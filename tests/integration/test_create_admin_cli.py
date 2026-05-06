"""Integration tests for ``scripts/create_admin.py``."""

from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.auth.security import PasswordHasher
from app.data.repositories.users import UserRepository
from app.db.base import Base
from scripts import create_admin as cli


def _bootstrap_db(tmp_path: Path) -> str:
    db_file = tmp_path / "create_admin_smoke.db"
    url = f"sqlite:///{db_file.as_posix()}"
    engine = create_engine(url)
    Base.metadata.create_all(bind=engine)
    engine.dispose()
    return url


def test_create_admin_inserts_user_with_hashed_password(tmp_path, capsys, monkeypatch):
    monkeypatch.setenv("ADMIN_PASSWORD", "hunter2!")
    monkeypatch.setenv("PASSWORD_HASH_N", "1024")
    url = _bootstrap_db(tmp_path)

    rc = cli.main(["--username", "alice", "--db-url", url])
    assert rc == 0

    captured = capsys.readouterr()
    assert "created user id=" in captured.out
    assert "username=alice" in captured.out
    # Plaintext password and hash are NEVER printed.
    assert "hunter2" not in captured.out
    assert "scrypt$" not in captured.out
    assert "scrypt$" not in captured.err

    engine = create_engine(url)
    try:
        with Session(engine, future=True) as session:
            user = UserRepository(session).get_by_username("alice")
    finally:
        engine.dispose()
    assert user is not None
    assert user.is_admin is True
    assert user.is_active is True
    # Password is properly hashed (scrypt prefix), never plaintext.
    assert user.password_hash.startswith("scrypt$")
    assert "hunter2" not in user.password_hash
    # And verifies cleanly via the hasher.
    hasher = PasswordHasher(n=1024, r=8, p=1)
    assert hasher.verify_password("hunter2!", user.password_hash)


def test_create_admin_duplicate_without_update_flag_fails(tmp_path, capsys, monkeypatch):
    monkeypatch.setenv("ADMIN_PASSWORD", "hunter2!")
    monkeypatch.setenv("PASSWORD_HASH_N", "1024")
    url = _bootstrap_db(tmp_path)

    assert cli.main(["--username", "alice", "--db-url", url]) == 0
    capsys.readouterr()  # discard

    rc = cli.main(["--username", "alice", "--db-url", url])
    assert rc == 1
    captured = capsys.readouterr()
    assert "already exists" in captured.err
    assert "scrypt$" not in captured.err
    assert "hunter2" not in captured.err


def test_create_admin_update_if_exists_replaces_credentials(tmp_path, capsys, monkeypatch):
    monkeypatch.setenv("PASSWORD_HASH_N", "1024")
    url = _bootstrap_db(tmp_path)

    monkeypatch.setenv("ADMIN_PASSWORD", "first-pass")
    assert cli.main(["--username", "alice", "--db-url", url]) == 0
    capsys.readouterr()

    monkeypatch.setenv("ADMIN_PASSWORD", "second-pass")
    rc = cli.main(
        ["--username", "alice", "--db-url", url, "--update-if-exists"],
    )
    assert rc == 0
    captured = capsys.readouterr()
    assert "updated user" in captured.out

    engine = create_engine(url)
    try:
        with Session(engine, future=True) as session:
            user = UserRepository(session).get_by_username("alice")
    finally:
        engine.dispose()
    assert user is not None
    hasher = PasswordHasher(n=1024, r=8, p=1)
    assert hasher.verify_password("second-pass", user.password_hash)
    assert not hasher.verify_password("first-pass", user.password_hash)


def test_create_admin_no_admin_flag_makes_regular_user(tmp_path, monkeypatch):
    monkeypatch.setenv("ADMIN_PASSWORD", "x")
    monkeypatch.setenv("PASSWORD_HASH_N", "1024")
    url = _bootstrap_db(tmp_path)

    rc = cli.main(["--username", "bob", "--db-url", url, "--no-admin"])
    assert rc == 0

    engine = create_engine(url)
    try:
        with Session(engine, future=True) as session:
            user = UserRepository(session).get_by_username("bob")
    finally:
        engine.dispose()
    assert user is not None
    assert user.is_admin is False


def test_create_admin_empty_password_fails(tmp_path, capsys, monkeypatch):
    monkeypatch.setenv("ADMIN_PASSWORD", "")
    monkeypatch.setenv("PASSWORD_HASH_N", "1024")
    url = _bootstrap_db(tmp_path)

    rc = cli.main(["--username", "alice", "--db-url", url])
    assert rc == 1
    captured = capsys.readouterr()
    assert "password must not be empty" in captured.err
