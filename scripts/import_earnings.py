"""Operator CLI for importing EarningsEvent CSV rows.

Default behaviour is dry-run: parse, validate, and count projected changes, then
rollback. Pass ``--commit`` to persist. This CLI never calls DART/KIS and rejects
body/raw/path/blob columns at header validation.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from sqlalchemy import create_engine

from app.config.settings import get_settings
from app.data.importers.earnings import (
    CsvForbiddenColumnError,
    CsvSchemaError,
    EarningsCsvImporter,
    ImportSummary,
)
from app.db.base import Base
from app.db.session import create_session_factory


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--file", required=True, help="Path to the input CSV file.")
    parser.add_argument(
        "--encoding",
        default="utf-8-sig",
        help="CSV encoding (default: utf-8-sig). Use cp949/euc-kr for legacy Excel exports.",
    )
    parser.add_argument(
        "--commit",
        action="store_true",
        help="Persist imported rows to the database. Default is dry-run rollback.",
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
    Base.metadata.create_all(engine)
    return create_session_factory(engine)


def run_import(
    *,
    file_path: str,
    commit: bool,
    encoding: str = "utf-8-sig",
    database_url: str | None = None,
) -> ImportSummary:
    factory = _build_session_factory(database_url)
    session = factory()
    try:
        importer = EarningsCsvImporter(session)
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
    print(f"Earnings import - {mode}")
    print(f"  file: {Path(file_path).name}")
    print(f"  total_rows       : {summary.total_rows}")
    print(f"  inserted         : {summary.inserted}")
    print(f"  updated          : {summary.updated}")
    print(f"  unchanged        : {summary.unchanged}")
    print(f"  validation_errors: {summary.validation_errors}")
    print(f"  truncated_notes  : {summary.truncated_notes}")
    if summary.error_details:
        print("  errors:")
        for row_idx, msg in summary.error_details[:20]:
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
    if args.commit and summary.validation_errors > 0:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
