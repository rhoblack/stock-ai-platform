"""Operator CLI wrapper around Alembic for the Stock AI Platform (v0.8 Phase A).

A thin, friendly wrapper over ``alembic <subcommand>`` that:

  * resolves the database URL the same way ``alembic/env.py`` does
    (``-x url=...`` override > ``alembic.ini`` > ``Settings.effective_database_url``),
  * defaults to **dry-run / inspect** subcommands -- ``current`` / ``history`` /
    ``heads`` -- so accidental ``upgrade`` against an operational DB requires
    an explicit subcommand,
  * surfaces the concrete commands operators typically need at release time:
    ``upgrade``, ``downgrade``, ``stamp``, ``current``, ``history``, ``heads``,
    ``offline-sql`` (== ``alembic upgrade head --sql`` for review).

This script never touches the database itself -- it only forwards to
``alembic.command``. It does not call KIS / DART / Telegram, does not place
orders, and does not import strategy / scoring / backtest code.

Examples
--------

    # Show the current revision on the dev SQLite DB.
    python -m scripts.migrate current

    # Upgrade a fresh DB to head (creates the 27 baseline tables).
    python -m scripts.migrate upgrade --to head

    # Stamp an existing DB at the baseline (no DDL, just bookkeeping).
    python -m scripts.migrate stamp --revision 0001_baseline_v0_7

    # Render the SQL alembic would emit (offline mode, no connection).
    python -m scripts.migrate offline-sql --to head

    # Override the URL for a one-off check against a disposable DB.
    python -m scripts.migrate current --db-url sqlite:///./trial.db
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from alembic import command
from alembic.config import Config

from app.config.settings import get_settings


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INI = PROJECT_ROOT / "alembic.ini"


def _build_config(db_url: str | None, ini_path: Path) -> Config:
    cfg = Config(str(ini_path))
    if db_url:
        # env.py reads -x url=... first.
        cfg.cmd_opts = type("Args", (), {"x": [f"url={db_url}"]})()  # type: ignore[attr-defined]
    return cfg


def _resolve_url(arg_url: str | None) -> str:
    if arg_url:
        return arg_url
    return get_settings().effective_database_url


def _add_common_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--db-url",
        default=None,
        help=(
            "Database URL override (passed to alembic via -x url=...). "
            "Defaults to Settings.effective_database_url (DATABASE_URL or "
            "SQLITE_DATABASE_URL)."
        ),
    )
    parser.add_argument(
        "--ini",
        type=Path,
        default=DEFAULT_INI,
        help="Path to alembic.ini (default: project root).",
    )


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_current = sub.add_parser("current", help="Print the current revision.")
    _add_common_args(p_current)

    p_history = sub.add_parser("history", help="Print the revision history.")
    _add_common_args(p_history)

    p_heads = sub.add_parser("heads", help="Print the head revision(s).")
    _add_common_args(p_heads)

    p_upgrade = sub.add_parser(
        "upgrade", help="Apply migrations up to a target (default: head)."
    )
    p_upgrade.add_argument("--to", default="head", help="Target revision (default: head).")
    _add_common_args(p_upgrade)

    p_downgrade = sub.add_parser(
        "downgrade",
        help=(
            "Revert migrations down to a target. Development / verification "
            "only -- production rollback uses backup restore."
        ),
    )
    p_downgrade.add_argument(
        "--to",
        required=True,
        help="Target revision (e.g. -1, base, or a specific revision id).",
    )
    _add_common_args(p_downgrade)

    p_stamp = sub.add_parser(
        "stamp",
        help=(
            "Mark the DB at a given revision without running DDL. Use for "
            "an existing operational DB that already contains the tables."
        ),
    )
    p_stamp.add_argument("--revision", required=True, help="Revision to stamp at.")
    _add_common_args(p_stamp)

    p_offline = sub.add_parser(
        "offline-sql",
        help=(
            "Render the SQL alembic would emit without connecting to the DB. "
            "Equivalent to `alembic upgrade <to> --sql`."
        ),
    )
    p_offline.add_argument("--to", default="head", help="Target revision (default: head).")
    _add_common_args(p_offline)

    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    url = _resolve_url(getattr(args, "db_url", None))
    ini_path = getattr(args, "ini", DEFAULT_INI)
    if not ini_path.exists():
        print(f"ERROR: alembic.ini not found at {ini_path}", file=sys.stderr)
        return 2

    cfg = _build_config(url, ini_path)

    print(f"[migrate] alembic.ini = {ini_path}")
    print(f"[migrate] database URL = {url}")
    print(f"[migrate] command = {args.cmd}")

    try:
        if args.cmd == "current":
            command.current(cfg, verbose=True)
        elif args.cmd == "history":
            command.history(cfg, verbose=True)
        elif args.cmd == "heads":
            command.heads(cfg, verbose=True)
        elif args.cmd == "upgrade":
            command.upgrade(cfg, args.to)
        elif args.cmd == "downgrade":
            command.downgrade(cfg, args.to)
        elif args.cmd == "stamp":
            command.stamp(cfg, args.revision)
        elif args.cmd == "offline-sql":
            command.upgrade(cfg, args.to, sql=True)
        else:  # pragma: no cover -- argparse already enforces this
            print(f"unknown command: {args.cmd}", file=sys.stderr)
            return 2
    except Exception as exc:
        print(f"[migrate] FAILED: {exc}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
