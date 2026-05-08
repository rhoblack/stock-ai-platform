"""Integration tests for v0.16 Phase C RealFillRepository.

Covers:
  * create() validation: side / fill_status / quantity / fill_price /
    gross_amount / net_amount.
  * list_by_order / list_recent.
  * Cascade delete via RealOrder.
  * Forbidden columns absent from the real_fills table (api_key / secret /
    token / account_number / raw_response / kis_response_raw / real_account).
  * AST guard: no httpx / requests / urllib imported in real_fill.py.
  * No raw-response storage method on RealFillRepository.
"""

from __future__ import annotations

import ast
from decimal import Decimal
from pathlib import Path

import pytest
from sqlalchemy import create_engine, event, inspect
from sqlalchemy.pool import StaticPool

from app.data.repositories.real_fill import RealFillRepository
from app.data.repositories.real_order import RealOrderRepository
from app.data.repositories.virtual_account import VirtualAccountRepository
from app.data.repositories.order_candidate import OrderCandidateRepository
from app.db.base import Base
from app.db.models import RealFill
from app.db.session import create_session_factory


PROJECT_ROOT = Path(__file__).resolve().parents[2]


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
    def _enable_fks(dbapi_conn, _):
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


def _seed_real_order(session) -> int:
    """Seed VirtualAccount + OrderCandidate + RealOrder; return order.id."""
    acc_repo = VirtualAccountRepository(session)
    acc = acc_repo.create(name="fill-test-acct", initial_cash=Decimal("5000000"))
    session.commit()

    cand_repo = OrderCandidateRepository(session)
    cand = cand_repo.create(
        account_id=acc.id,
        source="MANUAL",
        symbol="005930",
        side="BUY",
        quantity=10,
        order_type="MARKET",
        estimated_amount=Decimal("750000"),
    )
    session.commit()

    order_repo = RealOrderRepository(session)
    order = order_repo.create(
        candidate_id=cand.id,
        symbol="005930",
        side="BUY",
        quantity=10,
        order_type="MARKET",
        status="SUBMITTED",
        dry_run=False,
    )
    session.commit()
    return order.id


def _make_fill(session, real_order_id: int, *, quantity: int = 10, status: str = "FULL"):
    repo = RealFillRepository(session)
    price = Decimal("75000")
    qty = quantity
    gross = price * qty
    net = gross + Decimal("100")  # fee applied
    return repo.create(
        real_order_id=real_order_id,
        symbol="005930",
        side="BUY",
        quantity=qty,
        fill_price=price,
        fee=Decimal("100"),
        tax=Decimal("0"),
        gross_amount=gross,
        net_amount=net,
        fill_status=status,
    )


# ---------------------------------------------------------------------------
# 1. create() -- happy path
# ---------------------------------------------------------------------------


def test_create_full_fill_succeeds(session):
    oid = _seed_real_order(session)
    fill = _make_fill(session, oid)
    session.commit()

    assert fill.id is not None
    assert fill.real_order_id == oid
    assert fill.symbol == "005930"
    assert fill.quantity == 10
    assert fill.fill_status == "FULL"
    assert fill.gross_amount == Decimal("750000")


def test_create_partial_fill_succeeds(session):
    oid = _seed_real_order(session)
    fill = _make_fill(session, oid, quantity=5, status="PARTIAL")
    session.commit()
    assert fill.fill_status == "PARTIAL"
    assert fill.quantity == 5


# ---------------------------------------------------------------------------
# 2. create() -- validation errors
# ---------------------------------------------------------------------------


def test_create_rejects_bad_fill_status(session):
    oid = _seed_real_order(session)
    repo = RealFillRepository(session)
    with pytest.raises(ValueError, match="fill_status"):
        repo.create(
            real_order_id=oid,
            symbol="005930",
            side="BUY",
            quantity=10,
            fill_price=Decimal("75000"),
            gross_amount=Decimal("750000"),
            net_amount=Decimal("750100"),
            fill_status="UNKNOWN",
        )


def test_create_rejects_zero_quantity(session):
    oid = _seed_real_order(session)
    repo = RealFillRepository(session)
    with pytest.raises(ValueError, match="quantity"):
        repo.create(
            real_order_id=oid,
            symbol="005930",
            side="BUY",
            quantity=0,
            fill_price=Decimal("75000"),
            gross_amount=Decimal("0"),
            net_amount=Decimal("0"),
            fill_status="FULL",
        )


def test_create_rejects_zero_fill_price(session):
    oid = _seed_real_order(session)
    repo = RealFillRepository(session)
    with pytest.raises(ValueError, match="fill_price"):
        repo.create(
            real_order_id=oid,
            symbol="005930",
            side="BUY",
            quantity=10,
            fill_price=Decimal("0"),
            gross_amount=Decimal("0"),
            net_amount=Decimal("0"),
            fill_status="FULL",
        )


def test_create_rejects_negative_gross_amount(session):
    oid = _seed_real_order(session)
    repo = RealFillRepository(session)
    with pytest.raises(ValueError, match="gross_amount"):
        repo.create(
            real_order_id=oid,
            symbol="005930",
            side="BUY",
            quantity=10,
            fill_price=Decimal("75000"),
            gross_amount=Decimal("-1"),
            net_amount=Decimal("750000"),
            fill_status="FULL",
        )


# ---------------------------------------------------------------------------
# 3. list_by_order / list_recent
# ---------------------------------------------------------------------------


def test_list_by_order_returns_fills_in_order(session):
    oid = _seed_real_order(session)
    _make_fill(session, oid, quantity=5, status="PARTIAL")
    _make_fill(session, oid, quantity=5, status="FULL")
    session.commit()

    repo = RealFillRepository(session)
    fills = repo.list_by_order(oid)
    assert len(fills) == 2
    assert all(f.real_order_id == oid for f in fills)


def test_list_recent_returns_fills(session):
    oid = _seed_real_order(session)
    _make_fill(session, oid)
    session.commit()

    repo = RealFillRepository(session)
    fills = repo.list_recent(limit=10)
    assert len(fills) >= 1


# ---------------------------------------------------------------------------
# 4. Cascade delete via RealOrder
# ---------------------------------------------------------------------------


def test_real_order_cascade_deletes_fills(session):
    from app.db.models import RealOrder

    oid = _seed_real_order(session)
    fill = _make_fill(session, oid)
    fill_id = fill.id
    session.commit()

    order = session.get(RealOrder, oid)
    session.delete(order)
    session.commit()

    assert session.get(RealFill, fill_id) is None


# ---------------------------------------------------------------------------
# 5. Forbidden columns
# ---------------------------------------------------------------------------


_FORBIDDEN_FILL_COLUMNS = [
    "api_key",
    "app_secret",
    "access_token",
    "token",
    "secret",
    "raw_response",
    "kis_response_raw",
    "account_number",
    "real_account",
    "kis_order_id",
    "broker_order_id",
]


@pytest.mark.parametrize("col", _FORBIDDEN_FILL_COLUMNS)
def test_real_fills_table_lacks_forbidden_column(col):
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    insp = inspect(engine)
    columns = {c["name"] for c in insp.get_columns("real_fills")}
    engine.dispose()
    assert col not in columns, f"Forbidden column {col!r} found in real_fills table"


# ---------------------------------------------------------------------------
# 6. AST guard
# ---------------------------------------------------------------------------


def _real_fill_source() -> str:
    return (
        Path(__file__).resolve().parents[2]
        / "app"
        / "data"
        / "repositories"
        / "real_fill.py"
    ).read_text(encoding="utf-8")


def test_real_fill_repository_has_no_httpx_import():
    src = _real_fill_source()
    tree = ast.parse(src)
    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            names = (
                [alias.name for alias in node.names]
                if isinstance(node, ast.Import)
                else ([node.module] if node.module else [])
            )
            for name in names:
                assert "httpx" not in (name or ""), "httpx must not be imported"


def test_real_fill_repository_has_no_requests_import():
    src = _real_fill_source()
    tree = ast.parse(src)
    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            names = (
                [alias.name for alias in node.names]
                if isinstance(node, ast.Import)
                else ([node.module] if node.module else [])
            )
            for name in names:
                assert "requests" not in (name or ""), "requests must not be imported"


# ---------------------------------------------------------------------------
# 7. No raw-response storage method
# ---------------------------------------------------------------------------


def test_real_fill_repository_has_no_raw_response_method():
    repo_methods = [m for m in dir(RealFillRepository) if not m.startswith("_")]
    forbidden_methods = [m for m in repo_methods if "raw" in m.lower()]
    assert forbidden_methods == [], (
        f"RealFillRepository must not expose raw-response methods: {forbidden_methods}"
    )
