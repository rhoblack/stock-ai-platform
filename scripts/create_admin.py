"""Operator CLI for creating the v0.8 single-user admin account.

Examples
--------

    # Interactive prompt (recommended -- avoids password in shell history)
    python -m scripts.create_admin --username admin

    # Non-interactive via env var (suitable for ansible / CI / docker-compose)
    ADMIN_PASSWORD='hunter2!' python -m scripts.create_admin --username admin

    # Override DB target (otherwise reads Settings.effective_database_url)
    python -m scripts.create_admin --username admin --db-url sqlite:///./trial.db

    # Update existing user's password (idempotent re-run)
    python -m scripts.create_admin --username admin --update-if-exists

Safety
------

* Plaintext password is never logged or echoed back -- input goes via
  ``getpass`` or the ``ADMIN_PASSWORD`` env var (which the user controls).
* ``password_hash`` is never printed.
* ``password`` is purged from local variables as soon as the hash is computed.
* If the username already exists and ``--update-if-exists`` is NOT set, exits
  with code 1 and a "username already exists" message (no hash, no prompt to
  retry with a different name).
"""

from __future__ import annotations

import argparse
import getpass
import os
import sys

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.auth.security import PasswordHasher
from app.config.settings import get_settings
from app.data.repositories.users import UserRepository


PASSWORD_ENV_VAR = "ADMIN_PASSWORD"


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--username",
        required=True,
        help="Admin username (max 64 chars, must be unique).",
    )
    parser.add_argument(
        "--db-url",
        default=None,
        help=(
            "Database URL override. Defaults to "
            "Settings.effective_database_url (DATABASE_URL or SQLITE_DATABASE_URL)."
        ),
    )
    parser.add_argument(
        "--no-admin",
        action="store_true",
        help="Create the user without the is_admin flag (default: is_admin=True).",
    )
    parser.add_argument(
        "--update-if-exists",
        action="store_true",
        help=(
            "If a user with --username already exists, replace their password "
            "and is_admin / is_active flags. Default: exit with error."
        ),
    )
    parser.add_argument(
        "--password",
        default=None,
        help=(
            "Password (use of this flag exposes the password in shell history; "
            "prefer the ADMIN_PASSWORD env var or the interactive prompt)."
        ),
    )
    return parser.parse_args(argv)


def _read_password(cli_password: str | None) -> str:
    """Resolve the password from CLI > env var > interactive prompt.

    Never returns an empty password -- raises ``ValueError`` instead so the
    caller surfaces a non-zero exit.
    """
    candidate = cli_password
    if candidate is None:
        candidate = os.environ.get(PASSWORD_ENV_VAR)
    if candidate is None:
        candidate = getpass.getpass("password: ")
        confirm = getpass.getpass("password (confirm): ")
        if candidate != confirm:
            raise ValueError("passwords do not match")
    if not candidate:
        raise ValueError(
            "password must not be empty (set --password, ADMIN_PASSWORD env "
            "var, or supply via the interactive prompt)"
        )
    return candidate


def _resolve_url(arg_url: str | None) -> str:
    if arg_url:
        return arg_url
    return get_settings().effective_database_url


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    db_url = _resolve_url(args.db_url)

    try:
        password = _read_password(args.password)
    except ValueError as exc:
        print(f"[create_admin] ERROR: {exc}", file=sys.stderr)
        return 1

    hasher = PasswordHasher()
    password_hash = hasher.hash_password(password)
    # Drop plaintext from the local frame as early as possible.
    del password
    is_admin = not args.no_admin

    engine = create_engine(db_url)
    try:
        with Session(engine, future=True) as session:
            users = UserRepository(session)
            existing = users.get_by_username(args.username)
            if existing is not None and not args.update_if_exists:
                print(
                    f"[create_admin] ERROR: username {args.username!r} already "
                    "exists (use --update-if-exists to replace credentials)",
                    file=sys.stderr,
                )
                return 1
            if existing is not None:
                existing.password_hash = password_hash
                existing.is_admin = is_admin
                existing.is_active = True
                session.flush()
                user_id = existing.id
                action = "updated"
            else:
                created = users.create(
                    username=args.username,
                    password_hash=password_hash,
                    is_admin=is_admin,
                    is_active=True,
                )
                user_id = created.id
                action = "created"
            session.commit()
    finally:
        engine.dispose()
        # Clear the hash from the frame too -- not strictly secret, but no
        # reason to keep it around for the lifetime of the python process.
        password_hash = ""  # noqa: F841

    # SAFETY: never print the hash or the password.
    print(f"[create_admin] {action} user id={user_id} username={args.username}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
