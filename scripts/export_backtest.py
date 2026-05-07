"""Export a committed BacktestRun to CSV or JSON (safe fields only).

Only allow-listed fields are included.  The following are *never* exported:
evidence_json, config_json, summary_json, source_file_path, reason,
recommendation_id, recommendation_result_id, error_message, and any field
containing secrets or raw provenance data.

Exit codes
----------
  0 — success
  2 — usage error (missing run, bad arguments)

Usage examples
--------------
    python -m scripts.export_backtest --run-id 1
    python -m scripts.export_backtest --run-id 1 --format json
    python -m scripts.export_backtest --run-id 1 --format csv --output /tmp/out.csv
    python -m scripts.export_backtest --run-id 1 --dry-run
    python -m scripts.export_backtest --run-id 1 --db-url sqlite:///./local.db
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import sys
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import create_engine

from app.config.settings import get_settings
from app.data.repositories.backtest_results import BacktestResultRepository
from app.data.repositories.backtest_runs import BacktestRunRepository
from app.db.base import Base
from app.db.models import BacktestResult, BacktestRun
from app.db.session import create_session_factory


# ---------------------------------------------------------------------------
# Field whitelists — only these fields may appear in exported output.
# Evidence / provenance / secret fields are deliberately excluded.
# ---------------------------------------------------------------------------

_RUN_SAFE_FIELDS: tuple[str, ...] = (
    "id",
    "strategy_name",
    "strategy_version",
    "run_date",
    "start_date",
    "end_date",
    "signal_count",
    "buy_count",
    "avoid_count",
    "pass_count",
    "win_rate_1d",
    "win_rate_3d",
    "win_rate_5d",
    "win_rate_20d",
    "avg_return_1d",
    "avg_return_3d",
    "avg_return_5d",
    "avg_return_20d",
    "max_drawdown",
    "status",
)

_RESULT_SAFE_FIELDS: tuple[str, ...] = (
    "id",
    "backtest_run_id",
    "symbol",
    "signal_action",
    "confidence",
    "grade",
    "total_score",
    "return_1d",
    "return_3d",
    "return_5d",
    "return_20d",
    "cost_adjusted_return_5d",
    "regime",
    "result_status",
    "created_at",
)

# Denormalized CSV fieldnames: run fields (prefixed) + result fields.
_CSV_FIELDNAMES: tuple[str, ...] = (
    "run_id",
    "strategy_name",
    "strategy_version",
    "run_date",
    "run_start_date",
    "run_end_date",
    "run_status",
    "result_id",
    "symbol",
    "signal_action",
    "confidence",
    "grade",
    "total_score",
    "return_1d",
    "return_3d",
    "return_5d",
    "return_20d",
    "cost_adjusted_return_5d",
    "regime",
    "result_status",
    "created_at",
)

# Fields that MUST NEVER appear in export output regardless of whitelist changes.
FORBIDDEN_EXPORT_FIELDS: frozenset[str] = frozenset(
    {
        "evidence_json",
        "config_json",
        "summary_json",
        "source_file_path",
        "reason",
        "recommendation_id",
        "recommendation_result_id",
        "error_message",
        "secret",
        "token",
        "api_key",
        "password",
        "broker",
        "account",
        "order_id",
        "raw_text",
        "full_text",
        "body",
        "content",
    }
)


# ---------------------------------------------------------------------------
# Serialisation helpers
# ---------------------------------------------------------------------------


def _serialize(value: Any) -> str | None:
    """Convert Decimal / date / datetime to a plain string; None stays None."""
    if value is None:
        return None
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    return str(value)


def _result_to_csv_row(run: BacktestRun, result: BacktestResult) -> dict[str, str | None]:
    return {
        "run_id": _serialize(run.id),
        "strategy_name": _serialize(run.strategy_name),
        "strategy_version": _serialize(run.strategy_version),
        "run_date": _serialize(run.run_date),
        "run_start_date": _serialize(run.start_date),
        "run_end_date": _serialize(run.end_date),
        "run_status": _serialize(run.status),
        "result_id": _serialize(result.id),
        "symbol": _serialize(result.symbol),
        "signal_action": _serialize(result.signal_action),
        "confidence": _serialize(result.confidence),
        "grade": _serialize(result.grade),
        "total_score": _serialize(result.total_score),
        "return_1d": _serialize(result.return_1d),
        "return_3d": _serialize(result.return_3d),
        "return_5d": _serialize(result.return_5d),
        "return_20d": _serialize(result.return_20d),
        "cost_adjusted_return_5d": _serialize(result.cost_adjusted_return_5d),
        "regime": _serialize(result.regime),
        "result_status": _serialize(result.result_status),
        "created_at": _serialize(result.created_at),
    }


def _build_json_payload(run: BacktestRun, results: list[BacktestResult]) -> dict[str, Any]:
    run_dict: dict[str, Any] = {
        field: _serialize(getattr(run, field, None)) for field in _RUN_SAFE_FIELDS
    }
    result_rows: list[dict[str, Any]] = [
        {field: _serialize(getattr(r, field, None)) for field in _RESULT_SAFE_FIELDS}
        for r in results
    ]
    return {"run": run_dict, "results": result_rows}


def _build_csv_content(run: BacktestRun, results: list[BacktestResult]) -> str:
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=list(_CSV_FIELDNAMES), extrasaction="raise")
    writer.writeheader()
    for result in results:
        writer.writerow(_result_to_csv_row(run, result))
    return buf.getvalue()


# ---------------------------------------------------------------------------
# DB session helper (same pattern as scripts/run_backtest.py)
# ---------------------------------------------------------------------------


def _build_session_factory(database_url: str | None):
    url = database_url or get_settings().effective_database_url
    connect_args = {"check_same_thread": False} if url.startswith("sqlite") else {}
    engine = create_engine(url, connect_args=connect_args, future=True)
    Base.metadata.create_all(engine)
    return create_session_factory(engine)


# ---------------------------------------------------------------------------
# Public error type
# ---------------------------------------------------------------------------


class RunNotFoundError(Exception):
    """Raised when the requested BacktestRun.id does not exist in the DB."""


# ---------------------------------------------------------------------------
# Core export function (testable without CLI)
# ---------------------------------------------------------------------------


def export_backtest(
    *,
    run_id: int,
    fmt: str = "csv",
    output: str | None = None,
    dry_run: bool = False,
    database_url: str | None = None,
) -> str:
    """Export a BacktestRun and its BacktestResults to CSV or JSON.

    Parameters
    ----------
    run_id:       BacktestRun primary key.
    fmt:          "csv" (default) or "json".
    output:       Optional file path.  If None and not dry_run, writes to stdout.
    dry_run:      When True, returns serialized content without writing any file.
    database_url: SQLAlchemy URL override.  Defaults to settings.effective_database_url.

    Returns
    -------
    The serialized content string (CSV or JSON).

    Raises
    ------
    RunNotFoundError: when run_id is absent from the database.
    """
    factory = _build_session_factory(database_url)
    session = factory()
    try:
        run_repo = BacktestRunRepository(session)
        result_repo = BacktestResultRepository(session)

        run = run_repo.get_by_id(run_id)
        if run is None:
            raise RunNotFoundError(f"BacktestRun id={run_id} not found")

        results = result_repo.list_by_run(run_id)

        if fmt == "json":
            payload = _build_json_payload(run, results)
            content = json.dumps(payload, ensure_ascii=False, indent=2)
        else:
            content = _build_csv_content(run, results)

        if not dry_run:
            if output:
                with open(output, "w", encoding="utf-8", newline="") as fh:
                    fh.write(content)
            else:
                sys.stdout.write(content)

        return content
    finally:
        session.close()


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Export a BacktestRun to CSV or JSON (safe fields only).",
    )
    parser.add_argument(
        "--run-id",
        dest="run_id",
        type=int,
        required=True,
        help="BacktestRun.id to export (required).",
    )
    parser.add_argument(
        "--format",
        dest="fmt",
        choices=["csv", "json"],
        default="csv",
        help="Output format: csv (default) or json.",
    )
    parser.add_argument(
        "--output",
        dest="output",
        default=None,
        help="Output file path. Omit to write to stdout.",
    )
    parser.add_argument(
        "--dry-run",
        dest="dry_run",
        action="store_true",
        help="Build the export in memory without writing to disk.",
    )
    parser.add_argument(
        "--db-url",
        dest="db_url",
        default=None,
        help="SQLAlchemy URL override (default: settings.effective_database_url).",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    try:
        content = export_backtest(
            run_id=args.run_id,
            fmt=args.fmt,
            output=args.output,
            dry_run=args.dry_run,
            database_url=args.db_url,
        )
    except RunNotFoundError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    if args.dry_run:
        if args.fmt == "csv":
            row_count = max(content.count("\n") - 1, 0)
        else:
            try:
                row_count = len(json.loads(content).get("results", []))
            except Exception:
                row_count = 0
        print(
            f"[dry-run] run_id={args.run_id} fmt={args.fmt} "
            f"result_rows={row_count} bytes={len(content.encode('utf-8'))} "
            f"-- no file written",
            file=sys.stderr,
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
