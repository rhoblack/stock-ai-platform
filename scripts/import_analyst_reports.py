"""Operator CLI for importing analyst reports + themes + mappings + signal events.

Default behaviour is **dry-run**: parses + validates the CSV and prints a count
summary without writing to the DB. Pass ``--commit`` to actually persist rows.
The importer is idempotent (unique conflicts re-import as ``skipped_duplicates``)
so re-running ``--commit`` is safe.

Examples
--------

    # Validate only (DB unchanged)
    python -m scripts.import_analyst_reports --file reports.csv

    # Persist to DB
    python -m scripts.import_analyst_reports --file reports.csv --commit

    # Different encoding
    python -m scripts.import_analyst_reports --file reports.csv --encoding cp949

    # Override DB URL (e.g., point at a fresh sqlite for trial)
    python -m scripts.import_analyst_reports --file reports.csv --db-url sqlite:///./trial.db --commit

Copyright / compliance reminder
-------------------------------

The importer rejects (at header parse) any column that suggests full report
body text — ``body``, ``content``, ``full_text``, ``paragraph_text``,
``article_body``, ``raw_text``, ``html_body``, ``본문``, ``원문``, ``전문``, etc.
``summary`` is truncated to 500 chars. ``source_file_path`` is stored verbatim
so the operator can keep PDFs locally, but it is **never echoed to stdout** —
the CLI summary masks it.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from sqlalchemy import create_engine

from app.config.settings import get_settings
from app.data.importers.analyst_reports import (
    AnalystReportCsvImporter,
    CsvForbiddenColumnError,
    CsvSchemaError,
    ImportSummary,
)
from app.db.base import Base
from app.db.session import create_session_factory


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--file",
        required=True,
        help="Path to the input CSV file.",
    )
    parser.add_argument(
        "--encoding",
        default="utf-8-sig",
        help="CSV encoding (default: utf-8-sig — handles UTF-8 BOM and plain UTF-8). "
        "Use cp949 / euc-kr for legacy Excel exports.",
    )
    parser.add_argument(
        "--commit",
        action="store_true",
        help="Persist imported rows to the database. Default is dry-run "
        "(parse + validate + count, then rollback).",
    )
    parser.add_argument(
        "--db-url",
        dest="db_url",
        default=None,
        help="SQLAlchemy URL override (default: settings.effective_database_url).",
    )
    return parser.parse_args(argv)


def _build_session_factory(database_url: str | None):
    url = database_url or get_settings().effective_database_url
    connect_args = {"check_same_thread": False} if url.startswith("sqlite") else {}
    engine = create_engine(url, connect_args=connect_args, future=True)
    Base.metadata.create_all(engine)  # idempotent — does nothing if tables exist
    return create_session_factory(engine)


def run_import(
    *,
    file_path: str,
    commit: bool,
    encoding: str = "utf-8-sig",
    database_url: str | None = None,
) -> ImportSummary:
    """Programmatic entry point used by tests + the CLI."""
    factory = _build_session_factory(database_url)
    session = factory()
    try:
        importer = AnalystReportCsvImporter(session)
        summary = importer.import_file(file_path, encoding=encoding)
        if commit:
            session.commit()
        else:
            session.rollback()
    finally:
        session.close()
    return summary


def _print_summary(summary: ImportSummary, *, commit: bool, file_path: str) -> None:
    mode = "COMMIT (DB persisted)" if commit else "DRY-RUN (no DB writes)"
    # Mask any path so source_file_path-like operator paths never leak via the
    # filename either. The basename is enough for human context.
    masked_file = Path(file_path).name
    print(f"Analyst-report import — {mode}")
    print(f"  file: {masked_file}")
    print(f"  total_rows         : {summary.total_rows}")
    print(f"  inserted_reports   : {summary.inserted_reports}")
    print(f"  skipped_duplicates : {summary.skipped_duplicates}")
    print(f"  inserted_themes    : {summary.inserted_themes}")
    print(f"  inserted_mappings  : {summary.inserted_mappings}")
    print(f"  inserted_signal_events: {summary.inserted_signal_events}")
    print(f"  truncated_summaries: {summary.truncated_summaries}")
    print(f"  validation_errors  : {summary.validation_errors}")
    if summary.error_details:
        print("  errors:")
        for row_idx, msg in summary.error_details[:20]:
            # error message itself never includes source_file_path (importer
            # only echoes column names + the offending value for enums/dates)
            print(f"    row {row_idx}: {msg}")
        if len(summary.error_details) > 20:
            print(f"    ... and {len(summary.error_details) - 20} more")


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    try:
        summary = run_import(
            file_path=args.file,
            commit=args.commit,
            encoding=args.encoding,
            database_url=args.db_url,
        )
    except (CsvForbiddenColumnError, CsvSchemaError) as exc:
        print(f"CSV schema error: {exc}", file=sys.stderr)
        return 2
    except FileNotFoundError as exc:
        print(f"File not found: {exc}", file=sys.stderr)
        return 2

    _print_summary(summary, commit=args.commit, file_path=args.file)
    # Exit non-zero only when there were validation errors AND we tried to
    # commit — in dry-run we want a clean exit so the operator can review.
    if args.commit and summary.validation_errors > 0:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
