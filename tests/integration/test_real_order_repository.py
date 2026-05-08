"""Integration tests for v0.16 Phase C RealOrderRepository.

Covers:
  * create() validation: side / order_type / status / quantity / LIMIT requires
    limit_price / MARKET must not have limit_price.
  * get_by_id / get_by_candidate_id / list_recent / list_by_status.
  * update_status: allowed transitions / terminal-state block.
  * mark_submitted: broker_order_no_hash + submitted_at set.
  * mark_failed: error_message truncated to 500 / sensitive substring rejected.
  * mark_dry_run: transitions CREATED → DRY_RUN; rejected for other statuses.
  * dry_run defaults to True.
  * Cascade delete via OrderCandidate.
  * Forbidden columns absent from the ORM table (api_key / secret / token /
    account_number / raw_response / kis_response_raw / real_account).
  * AST guard: no httpx / requests / urllib imported in real_order.py.
  * No raw-response storage method on RealOrderRepository.
  * Phase D scope guard: real_order_executor.py not yet created.
"""

from __future__ import annotations

import ast
from decimal import Decimal
from pathlib import Path

import pytest
from sqlalchemy import create_engine, event, inspect
from sqlalchemy.pool import StaticPool

from app.data.repositories.real_order import (
    TERMINAL_STATUSES,
    VALID_SIDES,
    VALID_STATUSES,
    RealOrderRepository,
)
from app.data.repositories.virtual_account import VirtualAccountRepository
from app.data.repositories.order_candidate import OrderCandidateRepository
from app.db.base import Base
from app.db.models import RealOrder
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


def _seed_candidate(session) -> int:
    """Create a VirtualAccount + OrderCandidate and return candidate.id."""
    acc_repo = VirtualAccountRepository(session)
    acc = acc_repo.create(name="test-acct", initial_cash=Decimal("5000000"))
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
    return cand.id


# ---------------------------------------------------------------------------
# 1. create() -- happy path
# ---------------------------------------------------------------------------


def test_create_market_buy_dry_run_defaults(session):
    cid = _seed_candidate(session)
    repo = RealOrderRepository(session)
    order = repo.create(
        candidate_id=cid,
        symbol="005930",
        side="BUY",
        quantity=10,
        order_type="MARKET",
        estimated_amount=Decimal("750000"),
    )
    session.commit()

    assert order.id is not None
    assert order.symbol == "005930"
    assert order.side == "BUY"
    assert order.quantity == 10
    assert order.order_type == "MARKET"
    assert order.dry_run is True
    assert order.status == "DRY_RUN"
    assert order.limit_price is None


def test_create_limit_sell_order(session):
    cid = _seed_candidate(session)
    repo = RealOrderRepository(session)
    order = repo.create(
        candidate_id=cid,
        symbol="000660",
        side="SELL",
        quantity=5,
        order_type="LIMIT",
        limit_price=Decimal("150000"),
        estimated_amount=Decimal("750000"),
    )
    session.commit()
    assert order.limit_price == Decimal("150000")
    assert order.order_type == "LIMIT"


def test_create_with_fake_order_no(session):
    cid = _seed_candidate(session)
    repo = RealOrderRepository(session)
    order = repo.create(
        candidate_id=cid,
        symbol="005930",
        side="BUY",
        quantity=1,
        order_type="MARKET",
        fake_order_no="FAKE-000001",
    )
    session.commit()
    assert order.fake_order_no == "FAKE-000001"


# ---------------------------------------------------------------------------
# 2. create() -- validation errors
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("bad_side", ["buy", "SELL ", "short", ""])
def test_create_rejects_bad_side(session, bad_side):
    cid = _seed_candidate(session)
    repo = RealOrderRepository(session)
    with pytest.raises(ValueError, match="side"):
        repo.create(candidate_id=cid, symbol="005930", side=bad_side, quantity=1)


def test_create_rejects_zero_quantity(session):
    cid = _seed_candidate(session)
    repo = RealOrderRepository(session)
    with pytest.raises(ValueError, match="quantity"):
        repo.create(candidate_id=cid, symbol="005930", side="BUY", quantity=0)


def test_create_rejects_negative_quantity(session):
    cid = _seed_candidate(session)
    repo = RealOrderRepository(session)
    with pytest.raises(ValueError, match="quantity"):
        repo.create(candidate_id=cid, symbol="005930", side="BUY", quantity=-1)


def test_create_limit_without_price_raises(session):
    cid = _seed_candidate(session)
    repo = RealOrderRepository(session)
    with pytest.raises(ValueError, match="limit_price"):
        repo.create(
            candidate_id=cid,
            symbol="005930",
            side="BUY",
            quantity=5,
            order_type="LIMIT",
        )


def test_create_market_with_price_raises(session):
    cid = _seed_candidate(session)
    repo = RealOrderRepository(session)
    with pytest.raises(ValueError, match="limit_price"):
        repo.create(
            candidate_id=cid,
            symbol="005930",
            side="BUY",
            quantity=5,
            order_type="MARKET",
            limit_price=Decimal("75000"),
        )


# ---------------------------------------------------------------------------
# 3. get / list
# ---------------------------------------------------------------------------


def test_get_by_id_returns_none_for_missing(session):
    repo = RealOrderRepository(session)
    assert repo.get_by_id(9999) is None


def test_get_by_candidate_id_returns_all_orders(session):
    cid = _seed_candidate(session)
    repo = RealOrderRepository(session)
    repo.create(candidate_id=cid, symbol="005930", side="BUY", quantity=1)
    repo.create(candidate_id=cid, symbol="005930", side="BUY", quantity=2)
    session.commit()

    orders = repo.get_by_candidate_id(cid)
    assert len(orders) == 2


def test_list_recent_returns_latest_first(session):
    cid = _seed_candidate(session)
    repo = RealOrderRepository(session)
    o1 = repo.create(candidate_id=cid, symbol="005930", side="BUY", quantity=1)
    o2 = repo.create(candidate_id=cid, symbol="005930", side="BUY", quantity=2)
    session.commit()

    recent = repo.list_recent(limit=10)
    ids = [r.id for r in recent]
    assert ids.index(o2.id) < ids.index(o1.id)


def test_list_by_status_filters_correctly(session):
    cid = _seed_candidate(session)
    repo = RealOrderRepository(session)
    repo.create(candidate_id=cid, symbol="005930", side="BUY", quantity=1, status="DRY_RUN")
    repo.create(candidate_id=cid, symbol="005930", side="BUY", quantity=2, status="CREATED")
    session.commit()

    dry_run_orders = repo.list_by_status("DRY_RUN")
    assert all(o.status == "DRY_RUN" for o in dry_run_orders)

    created_orders = repo.list_by_status("CREATED")
    assert all(o.status == "CREATED" for o in created_orders)


# ---------------------------------------------------------------------------
# 4. update_status / terminal block
# ---------------------------------------------------------------------------


def test_update_status_transitions_allowed(session):
    cid = _seed_candidate(session)
    repo = RealOrderRepository(session)
    order = repo.create(
        candidate_id=cid, symbol="005930", side="BUY", quantity=1, status="CREATED"
    )
    session.commit()

    updated = repo.update_status(order, new_status="SUBMITTED")
    assert updated.status == "SUBMITTED"


def test_update_status_blocks_terminal_transition(session):
    cid = _seed_candidate(session)
    repo = RealOrderRepository(session)
    order = repo.create(
        candidate_id=cid, symbol="005930", side="BUY", quantity=1, status="DRY_RUN"
    )
    session.commit()

    with pytest.raises(ValueError, match="terminal"):
        repo.update_status(order, new_status="CREATED")


@pytest.mark.parametrize("terminal_status", sorted(TERMINAL_STATUSES))
def test_all_terminal_statuses_block_further_transitions(session, terminal_status):
    cid = _seed_candidate(session)
    repo = RealOrderRepository(session)
    order = repo.create(
        candidate_id=cid,
        symbol="005930",
        side="BUY",
        quantity=1,
        status=terminal_status,
    )
    session.commit()
    with pytest.raises(ValueError, match="terminal"):
        repo.update_status(order, new_status="CREATED")


# ---------------------------------------------------------------------------
# 5. mark_submitted
# ---------------------------------------------------------------------------


def test_mark_submitted_sets_hash_and_timestamp(session):
    cid = _seed_candidate(session)
    repo = RealOrderRepository(session)
    order = repo.create(
        candidate_id=cid, symbol="005930", side="BUY", quantity=1, status="CREATED"
    )
    session.commit()

    repo.mark_submitted(order, broker_order_no_hash="abc123hash")
    assert order.status == "SUBMITTED"
    assert order.broker_order_no_hash == "abc123hash"
    assert order.submitted_at is not None


# ---------------------------------------------------------------------------
# 6. mark_failed -- sensitive message guard
# ---------------------------------------------------------------------------


def test_mark_failed_sets_error_fields(session):
    cid = _seed_candidate(session)
    repo = RealOrderRepository(session)
    order = repo.create(
        candidate_id=cid, symbol="005930", side="BUY", quantity=1, status="CREATED"
    )
    session.commit()

    repo.mark_failed(order, error_code="TIMEOUT", error_message="Connection timed out")
    assert order.status == "FAILED"
    assert order.error_code == "TIMEOUT"
    assert order.error_message == "Connection timed out"


@pytest.mark.parametrize(
    "bad_msg",
    [
        "api_key=secret123",
        "APPSECRET=value",
        "access_token=abc",
        "account_no=12345",
    ],
)
def test_mark_failed_rejects_sensitive_message(session, bad_msg):
    cid = _seed_candidate(session)
    repo = RealOrderRepository(session)
    order = repo.create(
        candidate_id=cid, symbol="005930", side="BUY", quantity=1, status="CREATED"
    )
    session.commit()
    with pytest.raises(ValueError, match="sensitive"):
        repo.mark_failed(order, error_message=bad_msg)


def test_mark_failed_truncates_long_message(session):
    cid = _seed_candidate(session)
    repo = RealOrderRepository(session)
    order = repo.create(
        candidate_id=cid, symbol="005930", side="BUY", quantity=1, status="CREATED"
    )
    session.commit()

    long_msg = "x" * 600
    repo.mark_failed(order, error_message=long_msg)
    assert len(order.error_message) == 500


# ---------------------------------------------------------------------------
# 7. mark_dry_run
# ---------------------------------------------------------------------------


def test_mark_dry_run_transitions_created_to_dry_run(session):
    cid = _seed_candidate(session)
    repo = RealOrderRepository(session)
    order = repo.create(
        candidate_id=cid, symbol="005930", side="BUY", quantity=1, status="CREATED"
    )
    session.commit()

    repo.mark_dry_run(order, fake_order_no="FAKE-000001")
    assert order.status == "DRY_RUN"
    assert order.fake_order_no == "FAKE-000001"


def test_mark_dry_run_rejects_non_created_status(session):
    cid = _seed_candidate(session)
    repo = RealOrderRepository(session)
    order = repo.create(
        candidate_id=cid, symbol="005930", side="BUY", quantity=1, status="DRY_RUN"
    )
    session.commit()
    with pytest.raises(ValueError, match="CREATED"):
        repo.mark_dry_run(order)


# ---------------------------------------------------------------------------
# 8. Cascade delete
# ---------------------------------------------------------------------------


def test_candidate_cascade_deletes_real_order(session):
    from app.db.models import OrderCandidate

    cid = _seed_candidate(session)
    repo = RealOrderRepository(session)
    order = repo.create(
        candidate_id=cid, symbol="005930", side="BUY", quantity=1
    )
    order_id = order.id
    session.commit()

    cand = session.get(OrderCandidate, cid)
    session.delete(cand)
    session.commit()

    assert session.get(RealOrder, order_id) is None


# ---------------------------------------------------------------------------
# 9. Forbidden columns
# ---------------------------------------------------------------------------


_FORBIDDEN_COLUMNS = [
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


@pytest.mark.parametrize("col", _FORBIDDEN_COLUMNS)
def test_real_order_table_lacks_forbidden_column(col):
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    insp = inspect(engine)
    columns = {c["name"] for c in insp.get_columns("real_orders")}
    engine.dispose()
    assert col not in columns, f"Forbidden column {col!r} found in real_orders table"


# ---------------------------------------------------------------------------
# 10. AST guard -- no forbidden imports in real_order.py
# ---------------------------------------------------------------------------


def _real_order_source() -> str:
    return (
        Path(__file__).resolve().parents[2]
        / "app"
        / "data"
        / "repositories"
        / "real_order.py"
    ).read_text(encoding="utf-8")


def test_real_order_repository_has_no_httpx_import():
    src = _real_order_source()
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


def test_real_order_repository_has_no_requests_import():
    src = _real_order_source()
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


def test_real_order_repository_has_no_urllib_import():
    src = _real_order_source()
    tree = ast.parse(src)
    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            names = (
                [alias.name for alias in node.names]
                if isinstance(node, ast.Import)
                else ([node.module] if node.module else [])
            )
            for name in names:
                assert "urllib" not in (name or ""), "urllib must not be imported"


# ---------------------------------------------------------------------------
# 11. No raw-response storage method
# ---------------------------------------------------------------------------


def test_real_order_repository_has_no_raw_response_method():
    repo_methods = [m for m in dir(RealOrderRepository) if not m.startswith("_")]
    forbidden_methods = [m for m in repo_methods if "raw" in m.lower()]
    assert forbidden_methods == [], (
        f"RealOrderRepository must not expose raw-response methods: {forbidden_methods}"
    )


# ---------------------------------------------------------------------------
# 12. Phase D scope guard
# ---------------------------------------------------------------------------


def test_v016_phase_c_real_order_executor_not_yet_created():
    broker_dir = Path(__file__).resolve().parents[2] / "app" / "broker"
    assert not (broker_dir / "real_order_executor.py").exists(), (
        "real_order_executor.py must not exist in Phase C — it is a Phase D artefact"
    )
