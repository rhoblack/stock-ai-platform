"""Integration tests for v0.15 Phase B OrderCandidate repository + state machine.

Covers:
  * 8-state status machine: every allowed transition succeeds, every other
    transition (including all terminal-state outgoing edges) raises
    :class:`InvalidOrderCandidateTransition`.
  * ``OrderCandidateRepository.create`` validation: source / side /
    order_type / status enum, quantity > 0, LIMIT requires limit_price,
    estimated_amount >= 0, symbol normalisation (uppercase / trim).
  * ``attach_risk_result`` persists JSON; ``attach_virtual_order`` is
    idempotent and refuses overwriting with a different ``virtual_order_id``.
  * ``approve`` / ``reject`` / ``expire`` track approver / reason.
  * Cascade delete from VirtualAccount drops the candidate.
  * Forbidden columns (broker_order_id / kis_order_id / real_account /
    real_order_id / api_key / token / secret) are absent from the ORM table.
  * Source AST scan -- order_candidate.py imports nothing from KIS / DART /
    RSS / requests / httpx / urllib.
  * Alembic upgrade head + downgrade verification for 0007.
"""

from __future__ import annotations

import ast
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, event, inspect
from sqlalchemy.pool import StaticPool

from app.data.repositories.order_candidate import (
    InvalidOrderCandidateTransition,
    OrderCandidateRepository,
    OrderCandidateValidationError,
    TERMINAL_STATUSES,
    VALID_STATUSES,
)
from app.data.repositories.virtual_account import VirtualAccountRepository
from app.data.repositories.virtual_order import VirtualOrderRepository
from app.db.base import Base
from app.db.models import OrderCandidate
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


def _make_alembic_config(database_url: str) -> Config:
    cfg = Config(str(ALEMBIC_INI))
    cfg.cmd_opts = type("Args", (), {"x": [f"url={database_url}"]})()  # type: ignore[attr-defined]
    return cfg


def _seed_account(session, *, name="paper") -> int:
    repo = VirtualAccountRepository(session)
    acc = repo.create(name=name, initial_cash=Decimal("1000000"))
    session.commit()
    return acc.id


# ---------------------------------------------------------------------------
# create() validation
# ---------------------------------------------------------------------------


def test_create_market_buy_normalizes_symbol_to_upper(session):
    account_id = _seed_account(session)
    repo = OrderCandidateRepository(session)
    cand = repo.create(
        account_id=account_id,
        source="MANUAL",
        symbol=" 005930 ",
        side="BUY",
        quantity=10,
    )
    session.commit()
    assert cand.id is not None
    assert cand.symbol == "005930"
    assert cand.side == "BUY"
    assert cand.order_type == "MARKET"
    assert cand.limit_price is None
    assert cand.status == "DRAFT"


def test_create_limit_order_requires_price_and_persists_decimal(session):
    account_id = _seed_account(session)
    repo = OrderCandidateRepository(session)
    cand = repo.create(
        account_id=account_id,
        source="STRATEGY",
        symbol="005930",
        side="SELL",
        quantity=5,
        order_type="LIMIT",
        limit_price="71000",
        estimated_amount="355000",
    )
    session.commit()
    assert cand.order_type == "LIMIT"
    assert cand.limit_price == Decimal("71000")
    assert cand.estimated_amount == Decimal("355000")
    assert cand.side == "SELL"


@pytest.mark.parametrize(
    "kwargs,match",
    [
        (dict(source="OTHER", side="BUY", quantity=1), "source must be"),
        (dict(source="MANUAL", side="HOLD", quantity=1), "side must be"),
        (dict(source="MANUAL", side="BUY", quantity=0), "quantity must be > 0"),
        (dict(source="MANUAL", side="BUY", quantity=-3), "quantity must be > 0"),
        (
            dict(source="MANUAL", side="BUY", quantity=1, order_type="STOP"),
            "order_type must be",
        ),
        (
            dict(
                source="MANUAL",
                side="BUY",
                quantity=1,
                order_type="LIMIT",
            ),
            "LIMIT order requires limit_price",
        ),
        (
            dict(
                source="MANUAL",
                side="BUY",
                quantity=1,
                order_type="LIMIT",
                limit_price="0",
            ),
            "limit_price must be > 0",
        ),
        (
            dict(
                source="MANUAL",
                side="BUY",
                quantity=1,
                estimated_amount="-1",
            ),
            "estimated_amount must be >= 0",
        ),
        (
            dict(
                source="MANUAL",
                side="BUY",
                quantity=1,
                status="UNKNOWN",
            ),
            "status must be",
        ),
    ],
)
def test_create_rejects_invalid_inputs(session, kwargs, match):
    account_id = _seed_account(session)
    repo = OrderCandidateRepository(session)
    with pytest.raises(OrderCandidateValidationError, match=match):
        repo.create(account_id=account_id, symbol="005930", **kwargs)


def test_create_rejects_empty_symbol(session):
    account_id = _seed_account(session)
    repo = OrderCandidateRepository(session)
    with pytest.raises(OrderCandidateValidationError, match="symbol must be non-empty"):
        repo.create(
            account_id=account_id,
            source="MANUAL",
            symbol="   ",
            side="BUY",
            quantity=1,
        )


def test_market_order_ignores_supplied_limit_price(session):
    """A MARKET order must store NULL limit_price even if the caller passes one."""
    account_id = _seed_account(session)
    repo = OrderCandidateRepository(session)
    cand = repo.create(
        account_id=account_id,
        source="MANUAL",
        symbol="005930",
        side="BUY",
        quantity=10,
        order_type="MARKET",
        limit_price=Decimal("99999"),  # silently dropped
    )
    session.commit()
    assert cand.limit_price is None


# ---------------------------------------------------------------------------
# Read helpers
# ---------------------------------------------------------------------------


def test_list_by_account_filters_by_status_and_orders_desc(session):
    account_id = _seed_account(session)
    repo = OrderCandidateRepository(session)
    a = repo.create(account_id=account_id, source="MANUAL", symbol="005930", side="BUY", quantity=1)
    b = repo.create(account_id=account_id, source="MANUAL", symbol="000660", side="BUY", quantity=1)
    repo.update_status(b, new_status="RISK_CHECKING")
    session.commit()

    drafts = repo.list_by_account(account_id, status="DRAFT")
    assert [c.id for c in drafts] == [a.id]

    all_for_account = repo.list_by_account(account_id)
    assert [c.id for c in all_for_account] == [b.id, a.id]  # id desc


def test_list_pending_only_returns_pending_approval(session):
    account_id = _seed_account(session)
    repo = OrderCandidateRepository(session)
    cand = repo.create(account_id=account_id, source="MANUAL", symbol="005930", side="BUY", quantity=1)
    repo.update_status(cand, new_status="RISK_CHECKING")
    repo.update_status(cand, new_status="PENDING_APPROVAL")
    session.commit()

    pending = repo.list_pending()
    assert len(pending) == 1
    assert pending[0].id == cand.id


def test_list_expired_pending_returns_only_overdue(session):
    account_id = _seed_account(session)
    repo = OrderCandidateRepository(session)
    now = datetime(2026, 5, 8, 12, 0, tzinfo=timezone.utc)
    overdue = repo.create(
        account_id=account_id,
        source="MANUAL",
        symbol="005930",
        side="BUY",
        quantity=1,
        expires_at=now - timedelta(minutes=5),
    )
    fresh = repo.create(
        account_id=account_id,
        source="MANUAL",
        symbol="000660",
        side="BUY",
        quantity=1,
        expires_at=now + timedelta(minutes=5),
    )
    no_ttl = repo.create(
        account_id=account_id,
        source="MANUAL",
        symbol="035420",
        side="BUY",
        quantity=1,
    )
    for c in (overdue, fresh, no_ttl):
        repo.update_status(c, new_status="RISK_CHECKING")
        repo.update_status(c, new_status="PENDING_APPROVAL")
    session.commit()

    rows = repo.list_expired_pending(now=now)
    assert {c.id for c in rows} == {overdue.id}


# ---------------------------------------------------------------------------
# State machine -- allowed transitions
# ---------------------------------------------------------------------------


_ALLOWED_PATHS: list[tuple[str, ...]] = [
    ("DRAFT", "RISK_CHECKING", "RISK_REJECTED"),
    ("DRAFT", "RISK_CHECKING", "PENDING_APPROVAL", "APPROVED", "EXECUTED_PAPER"),
    ("DRAFT", "RISK_CHECKING", "PENDING_APPROVAL", "REJECTED"),
    ("DRAFT", "RISK_CHECKING", "PENDING_APPROVAL", "EXPIRED"),
]


@pytest.mark.parametrize("path", _ALLOWED_PATHS, ids=lambda p: " -> ".join(p))
def test_allowed_transition_paths(session, path):
    account_id = _seed_account(session)
    repo = OrderCandidateRepository(session)
    cand = repo.create(
        account_id=account_id,
        source="MANUAL",
        symbol="005930",
        side="BUY",
        quantity=1,
    )
    session.commit()
    assert cand.status == path[0]
    for next_state in path[1:]:
        repo.update_status(cand, new_status=next_state)
    session.commit()
    assert cand.status == path[-1]


# ---------------------------------------------------------------------------
# State machine -- forbidden transitions
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "from_state,to_state",
    [
        # DRAFT can only go to RISK_CHECKING
        ("DRAFT", "PENDING_APPROVAL"),
        ("DRAFT", "APPROVED"),
        ("DRAFT", "EXECUTED_PAPER"),
        ("DRAFT", "REJECTED"),
        ("DRAFT", "EXPIRED"),
        ("DRAFT", "RISK_REJECTED"),
        # RISK_CHECKING cannot skip ahead to APPROVED
        ("RISK_CHECKING", "APPROVED"),
        ("RISK_CHECKING", "EXECUTED_PAPER"),
        ("RISK_CHECKING", "REJECTED"),
        ("RISK_CHECKING", "EXPIRED"),
        # PENDING_APPROVAL cannot self-loop or skip to EXECUTED_PAPER
        ("PENDING_APPROVAL", "EXECUTED_PAPER"),
        ("PENDING_APPROVAL", "RISK_REJECTED"),
        ("PENDING_APPROVAL", "RISK_CHECKING"),
        ("PENDING_APPROVAL", "DRAFT"),
        # APPROVED can only go forward to EXECUTED_PAPER
        ("APPROVED", "REJECTED"),
        ("APPROVED", "EXPIRED"),
        ("APPROVED", "PENDING_APPROVAL"),
    ],
)
def test_forbidden_transitions_raise(session, from_state, to_state):
    """All edges NOT in the allowed adjacency must raise."""
    account_id = _seed_account(session)
    repo = OrderCandidateRepository(session)
    cand = repo.create(
        account_id=account_id, source="MANUAL", symbol="005930", side="BUY", quantity=1
    )
    # Drive the candidate into ``from_state`` via legal moves first.
    walk = {
        "DRAFT": (),
        "RISK_CHECKING": ("RISK_CHECKING",),
        "PENDING_APPROVAL": ("RISK_CHECKING", "PENDING_APPROVAL"),
        "APPROVED": ("RISK_CHECKING", "PENDING_APPROVAL", "APPROVED"),
    }[from_state]
    for s in walk:
        repo.update_status(cand, new_status=s)
    assert cand.status == from_state
    session.commit()

    with pytest.raises(InvalidOrderCandidateTransition):
        repo.update_status(cand, new_status=to_state)


@pytest.mark.parametrize("terminal", sorted(TERMINAL_STATUSES))
@pytest.mark.parametrize("target", sorted(VALID_STATUSES))
def test_terminal_states_refuse_every_outgoing_edge(session, terminal, target):
    """No transition out of terminal state is allowed -- including self-loops."""
    account_id = _seed_account(session)
    repo = OrderCandidateRepository(session)
    cand = repo.create(
        account_id=account_id, source="MANUAL", symbol="005930", side="BUY", quantity=1
    )
    # Drive into the terminal via legal path.
    if terminal == "RISK_REJECTED":
        repo.update_status(cand, new_status="RISK_CHECKING")
        repo.update_status(cand, new_status="RISK_REJECTED")
    elif terminal == "EXECUTED_PAPER":
        repo.update_status(cand, new_status="RISK_CHECKING")
        repo.update_status(cand, new_status="PENDING_APPROVAL")
        repo.update_status(cand, new_status="APPROVED")
        repo.update_status(cand, new_status="EXECUTED_PAPER")
    elif terminal == "REJECTED":
        repo.update_status(cand, new_status="RISK_CHECKING")
        repo.update_status(cand, new_status="PENDING_APPROVAL")
        repo.update_status(cand, new_status="REJECTED")
    elif terminal == "EXPIRED":
        repo.update_status(cand, new_status="RISK_CHECKING")
        repo.update_status(cand, new_status="PENDING_APPROVAL")
        repo.update_status(cand, new_status="EXPIRED")
    session.commit()
    assert cand.status == terminal

    with pytest.raises(InvalidOrderCandidateTransition):
        repo.update_status(cand, new_status=target)


def test_update_status_rejects_unknown_status(session):
    account_id = _seed_account(session)
    repo = OrderCandidateRepository(session)
    cand = repo.create(
        account_id=account_id, source="MANUAL", symbol="005930", side="BUY", quantity=1
    )
    with pytest.raises(OrderCandidateValidationError, match="status must be"):
        repo.update_status(cand, new_status="UNKNOWN")


# ---------------------------------------------------------------------------
# Domain helpers: approve / reject / expire / risk / virtual order
# ---------------------------------------------------------------------------


def test_attach_risk_result_persists_dict(session):
    account_id = _seed_account(session)
    repo = OrderCandidateRepository(session)
    cand = repo.create(
        account_id=account_id, source="MANUAL", symbol="005930", side="BUY", quantity=1
    )
    session.commit()

    result = {
        "passed": True,
        "violations": [],
        "policy_version": "pre-trade-v1",
        "evaluated_at": "2026-05-08T16:30:00+09:00",
    }
    repo.attach_risk_result(cand, result=result)
    session.commit()
    assert cand.risk_check_result_json == result


def test_attach_risk_result_rejects_non_dict(session):
    account_id = _seed_account(session)
    repo = OrderCandidateRepository(session)
    cand = repo.create(
        account_id=account_id, source="MANUAL", symbol="005930", side="BUY", quantity=1
    )
    with pytest.raises(OrderCandidateValidationError):
        repo.attach_risk_result(cand, result=["not", "a", "dict"])  # type: ignore[arg-type]


def test_attach_virtual_order_idempotent_then_overwrite_refused(session):
    account_id = _seed_account(session)
    cand_repo = OrderCandidateRepository(session)
    cand = cand_repo.create(
        account_id=account_id, source="MANUAL", symbol="005930", side="BUY", quantity=1
    )
    # Create two real virtual orders so the FK is satisfiable.
    orders = VirtualOrderRepository(session)
    vo1 = orders.create(account_id=account_id, symbol="005930", side="BUY", quantity=1)
    vo2 = orders.create(account_id=account_id, symbol="005930", side="BUY", quantity=1)
    session.commit()

    cand_repo.attach_virtual_order(cand, virtual_order_id=vo1.id)
    cand_repo.attach_virtual_order(cand, virtual_order_id=vo1.id)  # same id: ok
    session.commit()
    assert cand.virtual_order_id == vo1.id

    with pytest.raises(InvalidOrderCandidateTransition):
        cand_repo.attach_virtual_order(cand, virtual_order_id=vo2.id)


def test_approve_records_approver_and_status(session):
    from app.auth.security import PasswordHasher
    from app.data.repositories.users import UserRepository

    account_id = _seed_account(session)
    user = UserRepository(session).create(
        username="approver",
        password_hash=PasswordHasher(n=1024).hash_password("hunter2!"),
        is_admin=True,
    )
    session.commit()

    repo = OrderCandidateRepository(session)
    cand = repo.create(
        account_id=account_id, source="MANUAL", symbol="005930", side="BUY", quantity=1
    )
    repo.update_status(cand, new_status="RISK_CHECKING")
    repo.update_status(cand, new_status="PENDING_APPROVAL")
    session.commit()

    repo.approve(cand, approver_user_id=user.id)
    session.commit()
    assert cand.status == "APPROVED"
    assert cand.approver_user_id == user.id


def test_reject_records_reason_and_truncates(session):
    from app.auth.security import PasswordHasher
    from app.data.repositories.users import UserRepository

    account_id = _seed_account(session)
    user = UserRepository(session).create(
        username="rejecter",
        password_hash=PasswordHasher(n=1024).hash_password("hunter2!"),
        is_admin=True,
    )
    session.commit()

    repo = OrderCandidateRepository(session)
    cand = repo.create(
        account_id=account_id, source="MANUAL", symbol="005930", side="BUY", quantity=1
    )
    repo.update_status(cand, new_status="RISK_CHECKING")
    repo.update_status(cand, new_status="PENDING_APPROVAL")
    session.commit()

    long_reason = "x" * 500
    repo.reject(cand, approver_user_id=user.id, reason=long_reason)
    session.commit()
    assert cand.status == "REJECTED"
    assert cand.approver_user_id == user.id
    assert cand.rejection_reason is not None
    assert len(cand.rejection_reason) == 256  # truncated to column limit


def test_expire_marks_ttl_expired(session):
    account_id = _seed_account(session)
    repo = OrderCandidateRepository(session)
    cand = repo.create(
        account_id=account_id, source="MANUAL", symbol="005930", side="BUY", quantity=1
    )
    repo.update_status(cand, new_status="RISK_CHECKING")
    repo.update_status(cand, new_status="PENDING_APPROVAL")
    session.commit()

    repo.expire(cand)
    session.commit()
    assert cand.status == "EXPIRED"
    assert cand.rejection_reason == "ttl_expired"


# ---------------------------------------------------------------------------
# Cascade delete + forbidden columns
# ---------------------------------------------------------------------------


def test_cascade_delete_from_account(session):
    account_id = _seed_account(session)
    repo = OrderCandidateRepository(session)
    repo.create(
        account_id=account_id, source="MANUAL", symbol="005930", side="BUY", quantity=1
    )
    session.commit()

    accounts = VirtualAccountRepository(session)
    acc = accounts.get_by_id(account_id)
    session.delete(acc)
    session.commit()

    assert repo.list_by_account(account_id) == []


_FORBIDDEN_COLUMNS = (
    "broker_order_id",
    "kis_order_id",
    "real_account",
    "real_order_id",
    "api_key",
    "token",
    "secret",
)


def test_order_candidate_has_no_forbidden_columns():
    column_names = {col.key for col in OrderCandidate.__table__.columns}
    leaked = column_names & set(_FORBIDDEN_COLUMNS)
    assert leaked == set(), (
        f"order_candidates unexpectedly carries forbidden column(s): "
        f"{leaked!r}. v0.15 Phase B forbids {_FORBIDDEN_COLUMNS}."
    )


# ---------------------------------------------------------------------------
# AST guard: order_candidate.py imports nothing from KIS / external HTTP
# ---------------------------------------------------------------------------


def test_order_candidate_repository_has_no_forbidden_imports():
    src = (
        PROJECT_ROOT / "app" / "data" / "repositories" / "order_candidate.py"
    ).read_text(encoding="utf-8")
    tree = ast.parse(src)
    forbidden_modules = {"requests", "httpx", "urllib", "urllib3"}
    forbidden_prefixes = (
        "app.kis",
        "app.data.dart_provider",
        "app.data.rss_provider",
        "app.data.collectors.kis_client",
    )
    leaks: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for a in node.names:
                if a.name in forbidden_modules or any(
                    a.name == p or a.name.startswith(p + ".")
                    for p in forbidden_prefixes
                ):
                    leaks.append(f"import {a.name}")
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            if module in forbidden_modules or any(
                module == p or module.startswith(p + ".")
                for p in forbidden_prefixes
            ):
                leaks.append(f"from {module}")
    assert leaks == [], (
        f"order_candidate.py unexpectedly imports forbidden modules: {leaks!r}"
    )


# ---------------------------------------------------------------------------
# Alembic upgrade head + downgrade
# ---------------------------------------------------------------------------


def test_alembic_upgrade_head_creates_order_candidates_table(tmp_path):
    db_file = tmp_path / "v015_phase_b.db"
    url = f"sqlite:///{db_file.as_posix()}"
    cfg = _make_alembic_config(url)

    command.upgrade(cfg, "head")

    engine = create_engine(url)
    try:
        names = set(inspect(engine).get_table_names())
        cols = {c["name"] for c in inspect(engine).get_columns("order_candidates")}
    finally:
        engine.dispose()

    assert "order_candidates" in names
    expected_cols = {
        "id",
        "account_id",
        "source",
        "source_ref_id",
        "symbol",
        "side",
        "quantity",
        "order_type",
        "limit_price",
        "estimated_amount",
        "status",
        "risk_check_result_json",
        "approver_user_id",
        "rejection_reason",
        "expires_at",
        "virtual_order_id",
        "created_at",
        "updated_at",
    }
    assert expected_cols.issubset(cols)
    leaked = cols & set(_FORBIDDEN_COLUMNS)
    assert leaked == set()


def test_alembic_downgrade_phase_b_drops_only_order_candidates(tmp_path):
    db_file = tmp_path / "v015_phase_b_dn.db"
    url = f"sqlite:///{db_file.as_posix()}"
    cfg = _make_alembic_config(url)

    command.upgrade(cfg, "head")
    command.downgrade(cfg, "0006_virtual_positions")

    engine = create_engine(url)
    try:
        names = set(inspect(engine).get_table_names())
    finally:
        engine.dispose()

    assert "order_candidates" not in names
    # Phase A/B/C tables remain.
    assert "virtual_accounts" in names
    assert "virtual_orders" in names
    assert "virtual_positions" in names
    assert "virtual_pnl_snapshots" in names
