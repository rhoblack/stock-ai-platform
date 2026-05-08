"""Integration tests for v0.14 Phase B virtual trading core.

Covers:
  * VirtualAccountRepository CRUD
  * VirtualOrderRepository CRUD + idempotency uniqueness at DB level
  * Cascade delete from VirtualAccount drops its orders
  * SimulationBroker end-to-end: enabled / disabled / cancel / dedup
  * Forbidden columns: virtual_accounts and virtual_orders MUST NOT carry
    broker_order_id / kis_order_id / real_account / api_key / token / secret
  * ``alembic upgrade head`` against a fresh sqlite creates both tables
  * ``compare_metadata`` drift check is enforced by
    ``tests/integration/test_alembic_migration.py`` -- this file just
    spot-checks the new tables.
"""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, event, inspect
from sqlalchemy.exc import IntegrityError
from sqlalchemy.pool import StaticPool

from app.broker.simulation_broker import (
    PaperTradingDisabledError,
    SimulationBroker,
    SimulationBrokerError,
)
from app.config.settings import Settings
from app.data.repositories.virtual_account import VirtualAccountRepository
from app.data.repositories.virtual_order import VirtualOrderRepository
from app.db.base import Base
from app.db.models import VirtualAccount, VirtualOrder
from app.db.session import create_session_factory


PROJECT_ROOT = Path(__file__).resolve().parents[2]
ALEMBIC_INI = PROJECT_ROOT / "alembic.ini"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def session():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )

    @event.listens_for(engine, "connect")
    def _enable_fks(dbapi_conn, _):  # noqa: ANN001 - SQLA event signature
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    Base.metadata.create_all(engine)
    factory = create_session_factory(engine)
    db = factory()
    try:
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(engine)


def _settings(*, enabled: bool) -> Settings:
    return Settings(paper_trading_enabled=enabled)


def _make_alembic_config(database_url: str) -> Config:
    cfg = Config(str(ALEMBIC_INI))
    cfg.cmd_opts = type("Args", (), {"x": [f"url={database_url}"]})()  # type: ignore[attr-defined]
    return cfg


# ---------------------------------------------------------------------------
# VirtualAccountRepository
# ---------------------------------------------------------------------------


def test_virtual_account_create_defaults_cash_balance(session):
    repo = VirtualAccountRepository(session)
    acc = repo.create(name="paper", initial_cash=Decimal("5000000"))
    session.commit()

    assert acc.id is not None
    assert acc.cash_balance == Decimal("5000000")
    assert acc.initial_cash == Decimal("5000000")
    assert acc.currency == "KRW"
    assert acc.paper_trading_enabled is True


def test_virtual_account_rejects_empty_name(session):
    repo = VirtualAccountRepository(session)
    with pytest.raises(ValueError):
        repo.create(name="   ")


def test_virtual_account_rejects_negative_initial_cash(session):
    repo = VirtualAccountRepository(session)
    with pytest.raises(ValueError):
        repo.create(name="bad", initial_cash=Decimal("-1"))


def test_virtual_account_unique_user_name(session):
    # SQLite (and Postgres) treat NULLs as distinct in unique constraints,
    # so the (user_id, name) pair only collides when user_id IS NOT NULL.
    # Seed a real user row to exercise the constraint.
    from app.auth.security import PasswordHasher
    from app.data.repositories.users import UserRepository

    hasher = PasswordHasher(n=1024, r=8, p=1)
    user = UserRepository(session).create(
        username="acct-owner",
        password_hash=hasher.hash_password("hunter2!"),
        is_admin=True,
    )
    session.commit()

    repo = VirtualAccountRepository(session)
    repo.create(name="dup", user_id=user.id)
    session.commit()
    # The duplicate insert raises on flush (BaseRepository.add flushes
    # immediately), surfacing the unique constraint at create-time.
    with pytest.raises(IntegrityError):
        repo.create(name="dup", user_id=user.id)


def test_virtual_account_update_cash_balance(session):
    repo = VirtualAccountRepository(session)
    acc = repo.create(name="x")
    session.commit()

    repo.update_cash_balance(acc, new_balance=Decimal("9999"))
    session.commit()

    fresh = repo.get_by_id(acc.id)
    assert fresh is not None
    assert fresh.cash_balance == Decimal("9999")


# ---------------------------------------------------------------------------
# VirtualOrderRepository
# ---------------------------------------------------------------------------


def test_virtual_order_idempotency_key_unique_per_account(session):
    accounts = VirtualAccountRepository(session)
    a1 = accounts.create(name="a")
    a2 = accounts.create(name="b")
    session.commit()

    orders = VirtualOrderRepository(session)
    orders.create(
        account_id=a1.id,
        symbol="005930",
        side="BUY",
        quantity=1,
        idempotency_key="dup",
    )
    # Same key, *different* account is OK.
    orders.create(
        account_id=a2.id,
        symbol="005930",
        side="BUY",
        quantity=1,
        idempotency_key="dup",
    )
    session.commit()

    # Same key, same account → unique violation surfaces on flush
    # (BaseRepository.add flushes immediately).
    with pytest.raises(IntegrityError):
        orders.create(
            account_id=a1.id,
            symbol="005930",
            side="BUY",
            quantity=1,
            idempotency_key="dup",
        )


def test_virtual_order_cascade_delete_from_account(session):
    accounts = VirtualAccountRepository(session)
    acc = accounts.create(name="del-me")
    session.commit()

    orders = VirtualOrderRepository(session)
    orders.create(
        account_id=acc.id, symbol="005930", side="BUY", quantity=1
    )
    session.commit()

    session.delete(acc)
    session.commit()

    remaining = orders.list_by_account(acc.id)
    assert remaining == []


def test_virtual_order_repo_validates_inputs(session):
    accounts = VirtualAccountRepository(session)
    acc = accounts.create(name="x")
    session.commit()

    orders = VirtualOrderRepository(session)
    with pytest.raises(ValueError):
        orders.create(
            account_id=acc.id, symbol="005930", side="HOLD", quantity=1
        )
    with pytest.raises(ValueError):
        orders.create(
            account_id=acc.id, symbol="005930", side="BUY", quantity=0
        )
    with pytest.raises(ValueError):
        orders.create(
            account_id=acc.id,
            symbol="005930",
            side="BUY",
            quantity=1,
            order_type="LIMIT",
        )  # missing limit_price


def test_virtual_order_cancel_blocks_terminal_states(session):
    accounts = VirtualAccountRepository(session)
    acc = accounts.create(name="x")
    session.commit()
    orders = VirtualOrderRepository(session)
    order = orders.create(
        account_id=acc.id, symbol="005930", side="BUY", quantity=1
    )
    orders.update_status(order, new_status="FILLED")
    session.commit()

    with pytest.raises(ValueError):
        orders.cancel(order)


# ---------------------------------------------------------------------------
# SimulationBroker end-to-end
# ---------------------------------------------------------------------------


def test_broker_disabled_path_writes_nothing(session):
    accounts = VirtualAccountRepository(session)
    acc = accounts.create(name="paper")
    session.commit()

    broker = SimulationBroker(settings=_settings(enabled=False))
    with pytest.raises(PaperTradingDisabledError):
        broker.submit_order(
            session, account_id=acc.id, symbol="005930", side="BUY", quantity=1
        )

    assert VirtualOrderRepository(session).list_by_account(acc.id) == []


def test_broker_enabled_creates_and_cancels(session):
    accounts = VirtualAccountRepository(session)
    acc = accounts.create(name="paper")
    session.commit()

    broker = SimulationBroker(settings=_settings(enabled=True))
    submitted = broker.submit_order(
        session,
        account_id=acc.id,
        symbol="005930",
        side="BUY",
        quantity=10,
        idempotency_key="abc",
    )
    session.commit()
    assert submitted.order.status == "CREATED"

    canceled = broker.cancel_order(
        session, order_id=submitted.order.id, reason="ops cleanup"
    )
    session.commit()
    assert canceled.status == "CANCELED"
    assert canceled.reason == "ops cleanup"


def test_broker_idempotency_returns_existing_row_on_dup_key(session):
    accounts = VirtualAccountRepository(session)
    acc = accounts.create(name="paper")
    session.commit()

    broker = SimulationBroker(settings=_settings(enabled=True))
    a = broker.submit_order(
        session,
        account_id=acc.id,
        symbol="005930",
        side="BUY",
        quantity=10,
        idempotency_key="dup",
    )
    session.commit()
    b = broker.submit_order(
        session,
        account_id=acc.id,
        symbol="005930",
        side="BUY",
        quantity=10,
        idempotency_key="dup",
    )
    session.commit()

    assert b.deduplicated is True
    assert b.order.id == a.order.id

    rows = VirtualOrderRepository(session).list_by_account(acc.id)
    assert len(rows) == 1


# ---------------------------------------------------------------------------
# Forbidden columns
# ---------------------------------------------------------------------------


_FORBIDDEN_COLUMNS = (
    "broker_order_id",
    "kis_order_id",
    "real_account",
    "api_key",
    "token",
    "secret",
)


@pytest.mark.parametrize("model", [VirtualAccount, VirtualOrder])
def test_models_have_no_forbidden_columns(model):
    column_names = {col.key for col in model.__table__.columns}
    leaked = column_names & set(_FORBIDDEN_COLUMNS)
    assert leaked == set(), (
        f"{model.__tablename__} unexpectedly carries forbidden column(s): "
        f"{leaked!r}. v0.14 Phase B forbids {_FORBIDDEN_COLUMNS}."
    )


# ---------------------------------------------------------------------------
# Alembic upgrade head creates the new tables on a fresh DB
# ---------------------------------------------------------------------------


def test_alembic_upgrade_head_creates_virtual_trading_tables(tmp_path):
    db_file = tmp_path / "v014_phase_b.db"
    url = f"sqlite:///{db_file.as_posix()}"
    cfg = _make_alembic_config(url)

    command.upgrade(cfg, "head")

    engine = create_engine(url)
    try:
        names = set(inspect(engine).get_table_names())
        # Spot-check the two new tables and a few of their columns.
        assert "virtual_accounts" in names
        assert "virtual_orders" in names

        account_cols = {
            c["name"] for c in inspect(engine).get_columns("virtual_accounts")
        }
        order_cols = {
            c["name"] for c in inspect(engine).get_columns("virtual_orders")
        }
    finally:
        engine.dispose()

    expected_account_cols = {
        "id",
        "user_id",
        "name",
        "initial_cash",
        "cash_balance",
        "currency",
        "paper_trading_enabled",
        "created_at",
        "updated_at",
    }
    expected_order_cols = {
        "id",
        "account_id",
        "symbol",
        "side",
        "quantity",
        "order_type",
        "limit_price",
        "status",
        "idempotency_key",
        "reason",
        "note",
        "created_at",
        "updated_at",
    }
    assert expected_account_cols.issubset(account_cols)
    assert expected_order_cols.issubset(order_cols)

    leaked_account = account_cols & set(_FORBIDDEN_COLUMNS)
    leaked_orders = order_cols & set(_FORBIDDEN_COLUMNS)
    assert leaked_account == set()
    assert leaked_orders == set()


def test_alembic_downgrade_drops_virtual_trading_tables(tmp_path):
    db_file = tmp_path / "v014_phase_b_dn.db"
    url = f"sqlite:///{db_file.as_posix()}"
    cfg = _make_alembic_config(url)

    command.upgrade(cfg, "head")
    command.downgrade(cfg, "0004_user_preferences")

    engine = create_engine(url)
    try:
        names = set(inspect(engine).get_table_names())
    finally:
        engine.dispose()

    assert "virtual_accounts" not in names
    assert "virtual_orders" not in names
    # Earlier tables must remain intact.
    assert "user_preferences" in names
    assert "users" in names
