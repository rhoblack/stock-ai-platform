"""Operator CLI for running v0.7 BacktestEngine against existing recommendations.

Default behaviour is dry-run: build snapshots, evaluate the chosen strategy,
report counts + win-rate + avg-return + missing-horizon counts, then rollback.
Pass ``--commit`` to persist a ``BacktestRun`` + N ``BacktestResult`` rows.

This CLI **never** calls KIS / DART / Telegram and **never** places orders. It
only reads from existing tables (``recommendations``, ``recommendation_results``,
``data_snapshots``) and writes (when committed) to the new ``backtest_runs`` /
``backtest_results`` tables.

Examples
--------

    python -m scripts.run_backtest --strategy top_grade
    python -m scripts.run_backtest --strategy high_score --from-date 2026-04-01
    python -m scripts.run_backtest --strategy multi_signal --from-date 2026-04-01 --to-date 2026-05-04 --commit
    python -m scripts.run_backtest --strategy top_grade --db-url sqlite:///./trial.db --limit 50 --commit
"""

from __future__ import annotations

import argparse
import sys
from datetime import date, datetime
from typing import Any

from sqlalchemy import create_engine

from app.backtest.engine import BacktestEngine, BacktestRunSummary
from app.config.settings import get_settings
from app.db.base import Base
from app.db.session import create_session_factory
from app.strategy.registry import (
    KNOWN_STRATEGIES,
    UnknownStrategyError,
    get_strategy,
)


def _parse_date(raw: str | None) -> date | None:
    if raw is None:
        return None
    try:
        return datetime.strptime(raw, "%Y-%m-%d").date()
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"invalid date {raw!r}; expected YYYY-MM-DD") from exc


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--strategy",
        required=True,
        choices=KNOWN_STRATEGIES,
        help=f"Strategy name (one of: {', '.join(KNOWN_STRATEGIES)})",
    )
    parser.add_argument(
        "--from-date",
        dest="from_date",
        type=_parse_date,
        default=None,
        help="Inclusive lower bound on RecommendationRun.run_date (YYYY-MM-DD).",
    )
    parser.add_argument(
        "--to-date",
        dest="to_date",
        type=_parse_date,
        default=None,
        help="Inclusive upper bound on RecommendationRun.run_date (YYYY-MM-DD).",
    )
    parser.add_argument(
        "--commit",
        action="store_true",
        help="Persist BacktestRun + BacktestResult rows. Default is dry-run rollback.",
    )
    parser.add_argument(
        "--db-url",
        dest="db_url",
        default=None,
        help="SQLAlchemy URL override (default: settings.effective_database_url).",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Cap evaluated recommendations (most recent first). Default: no cap.",
    )
    return parser.parse_args(argv)


def _build_session_factory(database_url: str | None):
    url = database_url or get_settings().effective_database_url
    connect_args = {"check_same_thread": False} if url.startswith("sqlite") else {}
    engine = create_engine(url, connect_args=connect_args, future=True)
    Base.metadata.create_all(engine)
    return create_session_factory(engine)


def run_backtest(
    *,
    strategy_name: str,
    commit: bool,
    from_date: date | None = None,
    to_date: date | None = None,
    limit: int | None = None,
    database_url: str | None = None,
) -> BacktestRunSummary:
    factory = _build_session_factory(database_url)
    session = factory()
    try:
        strategy = get_strategy(strategy_name)
        engine = BacktestEngine(session)
        summary = engine.run(
            strategy=strategy,
            start_date=from_date,
            end_date=to_date,
            limit=limit,
            dry_run=not commit,
        )
        if commit:
            session.commit()
        else:
            session.rollback()
    finally:
        session.close()
    return summary


def _print_summary(summary: BacktestRunSummary, *, commit: bool) -> None:
    mode = "COMMIT (DB persisted)" if commit else "DRY-RUN (no DB writes)"
    print(f"Backtest - {mode}")
    print(f"  strategy_name                 : {summary.strategy_name}")
    print(f"  strategy_version              : {summary.strategy_version}")
    print(f"  run_date                      : {summary.run_date}")
    print(f"  start_date                    : {summary.start_date}")
    print(f"  end_date                      : {summary.end_date}")
    print(f"  evaluated_recommendation_count: {summary.evaluated_recommendation_count}")
    print(f"  signal_count                  : {summary.signal_count}")
    print(f"  buy_count                     : {summary.buy_count}")
    print(f"  pass_count                    : {summary.pass_count}")
    print(f"  avoid_count                   : {summary.avoid_count}")
    for horizon in (1, 3, 5, 20):
        wr = getattr(summary, f"win_rate_{horizon}d")
        ar = getattr(summary, f"avg_return_{horizon}d")
        print(
            f"  {horizon:>3}d                          : "
            f"win_rate={_fmt(wr)}  avg_return={_fmt(ar)}",
        )
    print(f"  max_drawdown                  : {_fmt(summary.max_drawdown)}")
    print(f"  cost_model_version            : {summary.cost_model_version}")
    print(f"  total_cost (fraction)         : {_fmt(summary.total_cost)}")
    print(
        f"  cost_adjusted_avg_return_5d   : {_fmt(summary.cost_adjusted_avg_return_5d)}",
    )
    if summary.regime_breakdown:
        print("  regime_breakdown              :")
        for entry in summary.regime_breakdown:
            print(
                f"    - {entry.regime:<14}  buy={entry.buy_count:<3}  "
                f"win_rate_5d={_fmt(entry.win_rate_5d)}  "
                f"avg_return_5d={_fmt(entry.avg_return_5d)}  "
                f"cost_adj={_fmt(entry.cost_adjusted_avg_return_5d)}",
            )
    if summary.missing_result_count_per_horizon:
        for horizon, count in sorted(summary.missing_result_count_per_horizon.items()):
            print(f"  missing_result_count[{horizon}d]      : {count}")
    if summary.backtest_run_id is not None:
        print(f"  backtest_run_id               : {summary.backtest_run_id}")
    print(f"  notes                         : {summary.notes}")


def _fmt(value: Any) -> str:
    return "—" if value is None else str(value)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    try:
        summary = run_backtest(
            strategy_name=args.strategy,
            commit=args.commit,
            from_date=args.from_date,
            to_date=args.to_date,
            limit=args.limit,
            database_url=args.db_url,
        )
    except UnknownStrategyError as exc:
        print(f"Strategy error: {exc}", file=sys.stderr)
        return 2

    _print_summary(summary, commit=args.commit)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
