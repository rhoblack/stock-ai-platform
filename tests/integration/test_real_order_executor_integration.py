"""Integration tests for v1.0 Phase C — RealOrderExecutor real path with HttpxKisOrderTransport.

These tests exercise the full chain end-to-end:
    candidate → 10-gate → real path → HttpxKisOrderTransport (respx-mocked)
    → mark_submitted/mark_failed → ApprovalAuditLog row.

All HTTP interactions are mocked via ``httpx.MockTransport``; the test
suite issues ZERO real KIS calls. The ``HttpxKisOrderTransport`` instance
is built with a respx-backed ``httpx.Client`` and injected directly into
the executor, mirroring the wiring that v1.0 Phase D will use in
production code paths.

Hard guarantees verified
------------------------
* Real outbound traffic = 0 (httpx.MockTransport intercepts all calls).
* Plaintext KIS order_no NEVER appears in DB rows or audit details.
* RealOrder.broker_order_no_hash is exactly 64 hex chars (SHA-256).
* ApprovalAuditLog REAL_ORDER_SUBMITTED / REAL_ORDER_FAILED rows match
  the executor outcome 1:1.
"""

from __future__ import annotations

import hashlib
from decimal import Decimal

import httpx
import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.pool import StaticPool

from app.broker.kis_order_transport_real import HttpxKisOrderTransport
from app.broker.real_order_executor import RealOrderExecutor
from app.config.settings import Settings
from app.data.repositories.approval_audit_log import ApprovalAuditLogRepository
from app.data.repositories.order_candidate import OrderCandidateRepository
from app.data.repositories.real_order import RealOrderRepository
from app.data.repositories.virtual_account import VirtualAccountRepository
from app.db.base import Base
from app.db.models import RealOrder
from app.db.session import create_session_factory


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
    def _fk(dbapi_conn, _):
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


def _make_real_settings(**overrides) -> Settings:
    base = dict(
        kill_switch_enabled=False,
        trading_safety_enabled=True,
        real_trading_enabled=True,
        kis_order_enabled=True,
        real_order_dry_run=False,
        max_real_order_amount=5_000_000,
        max_real_daily_order_amount=50_000_000,
        approval_required=True,
        max_order_amount=5_000_000,
        max_daily_order_amount=50_000_000,
        max_position_ratio=0.80,
        max_daily_loss_amount=5_000_000,
        kis_account_no="000000000012",  # 12-char test account
        kis_app_key="kis-test-app-key-XYZ",
        kis_app_secret="kis-test-app-secret-XYZ",
    )
    base.update(overrides)
    return Settings(**base)


def _seed_candidate(session) -> int:
    acc_repo = VirtualAccountRepository(session)
    acc = acc_repo.create(
        name="phase-c-int-test", initial_cash=Decimal("10_000_000")
    )
    session.commit()

    cand_repo = OrderCandidateRepository(session)
    cand = cand_repo.create(
        account_id=acc.id,
        source="MANUAL",
        symbol="005930",
        side="BUY",
        quantity=10,
        order_type="MARKET",
        estimated_amount=Decimal("750_000"),
    )
    cand_repo.update_status(cand, new_status="RISK_CHECKING")
    cand_repo.update_status(cand, new_status="PENDING_APPROVAL")
    cand_repo.update_status(cand, new_status="APPROVED")
    session.commit()
    return cand.id


def _build_transport(handler, settings) -> HttpxKisOrderTransport:
    client = httpx.Client(
        base_url=settings.kis_order_base_url,
        transport=httpx.MockTransport(handler),
        timeout=10.0,
    )
    return HttpxKisOrderTransport(
        settings=settings,
        client=client,
        app_key=settings.kis_app_key,
        app_secret=settings.kis_app_secret,
        access_token="test-access-token-XYZ",
        account_no=settings.kis_account_no,
    )


# ---------------------------------------------------------------------------
# 1. Real path SUBMITTED end-to-end
# ---------------------------------------------------------------------------


def test_int_real_path_submitted_writes_real_order_and_audit(session):
    cid = _seed_candidate(session)
    settings = _make_real_settings()

    captured = {"reqs": 0}
    plaintext_order_no = "INT-REAL-001"

    def handler(request):
        captured["reqs"] += 1
        return httpx.Response(
            200,
            json={
                "rt_cd": "0",
                "msg_cd": "OPSP0000",
                "msg1": "정상처리",
                "output": {"ODNO": plaintext_order_no, "KRX_FWDG_ORD_ORGNO": "00950"},
            },
        )

    transport = _build_transport(handler, settings)
    executor = RealOrderExecutor(transport=transport)

    result = executor.execute(session, candidate_id=cid, settings=settings)
    session.commit()

    # Outbound HTTP happened exactly once (place_order retry=0)
    assert captured["reqs"] == 1
    assert result.success is True
    assert result.status == "SUBMITTED"

    order = session.get(RealOrder, result.real_order_id)
    assert order.dry_run is False
    assert order.status == "SUBMITTED"
    expected_hash = hashlib.sha256(plaintext_order_no.encode()).hexdigest()
    assert order.broker_order_no_hash == expected_hash
    assert len(order.broker_order_no_hash) == 64

    # Plaintext is gone from EVERY persisted column.
    assert plaintext_order_no not in (order.broker_order_no_hash or "")
    assert plaintext_order_no not in (order.fake_order_no or "")
    assert plaintext_order_no not in (order.error_message or "")

    audit_repo = ApprovalAuditLogRepository(session)
    rows = [
        r for r in audit_repo.list_by_candidate(cid)
        if r.event_type == "REAL_ORDER_SUBMITTED"
    ]
    assert len(rows) == 1
    details = rows[0].details_json
    assert details["classification"] == "SUBMITTED"
    assert details["dry_run"] is False
    # Plaintext must not appear in the audit details either.
    assert plaintext_order_no not in str(details)


# ---------------------------------------------------------------------------
# 2. Real path REJECTED (HTTP 4xx)
# ---------------------------------------------------------------------------


def test_int_real_path_4xx_rejected_writes_failed(session):
    cid = _seed_candidate(session)
    settings = _make_real_settings()

    def handler(request):
        return httpx.Response(403, text="forbidden")

    transport = _build_transport(handler, settings)
    executor = RealOrderExecutor(transport=transport)
    result = executor.execute(session, candidate_id=cid, settings=settings)
    session.commit()

    assert result.success is False
    assert result.status == "FAILED"
    assert result.blocked_reason == "REJECTED"

    order = session.get(RealOrder, result.real_order_id)
    assert order.status == "FAILED"
    assert order.error_code == "REJECTED"
    assert order.broker_order_no_hash is None

    audit_repo = ApprovalAuditLogRepository(session)
    failed_rows = [
        r for r in audit_repo.list_by_candidate(cid)
        if r.event_type == "REAL_ORDER_FAILED"
    ]
    assert len(failed_rows) == 1
    assert failed_rows[0].details_json["classification"] == "REJECTED"


# ---------------------------------------------------------------------------
# 3. Real path UNKNOWN (HTTP 5xx)
# ---------------------------------------------------------------------------


def test_int_real_path_5xx_unknown_writes_failed(session):
    cid = _seed_candidate(session)
    settings = _make_real_settings()

    def handler(request):
        return httpx.Response(503, text="service unavailable")

    transport = _build_transport(handler, settings)
    executor = RealOrderExecutor(transport=transport)
    result = executor.execute(session, candidate_id=cid, settings=settings)
    session.commit()

    assert result.success is False
    assert result.blocked_reason == "UNKNOWN"
    order = session.get(RealOrder, result.real_order_id)
    assert order.error_code == "UNKNOWN"


# ---------------------------------------------------------------------------
# 4. Real path TIMEOUT (transport-layer)
# ---------------------------------------------------------------------------


def test_int_real_path_timeout_writes_failed(session):
    cid = _seed_candidate(session)
    settings = _make_real_settings()

    def handler(request):
        raise httpx.ConnectTimeout("simulated timeout", request=request)

    transport = _build_transport(handler, settings)
    executor = RealOrderExecutor(transport=transport)
    result = executor.execute(session, candidate_id=cid, settings=settings)
    session.commit()

    assert result.success is False
    assert result.blocked_reason == "TIMEOUT"
    order = session.get(RealOrder, result.real_order_id)
    assert order.error_code == "TIMEOUT"
    assert order.broker_order_no_hash is None


# ---------------------------------------------------------------------------
# 5. Business-error rt_cd != 0 (HTTP 200 + KIS rejection)
# ---------------------------------------------------------------------------


def test_int_real_path_business_error_writes_failed(session):
    cid = _seed_candidate(session)
    settings = _make_real_settings()

    def handler(request):
        return httpx.Response(
            200,
            json={
                "rt_cd": "1",
                "msg_cd": "EGW00123",
                "msg1": "주문 가능 수량을 초과했습니다.",
            },
        )

    transport = _build_transport(handler, settings)
    executor = RealOrderExecutor(transport=transport)
    result = executor.execute(session, candidate_id=cid, settings=settings)
    session.commit()

    assert result.blocked_reason == "REJECTED"
    order = session.get(RealOrder, result.real_order_id)
    assert order.error_code == "REJECTED"


# ---------------------------------------------------------------------------
# 6. RealOrder anchor row exists BEFORE the transport call
# ---------------------------------------------------------------------------


def test_int_real_order_anchor_row_persisted_before_kis_call(session):
    """The CREATED-state row must be visible from the transport perspective.

    This guarantees that even if the network response is lost, the operator
    can see an in-flight RealOrder row and follow RUNBOOK §5 to reconcile.
    """
    cid = _seed_candidate(session)
    settings = _make_real_settings()
    rows_at_request_time: list[int] = []

    def handler(request):
        rows_at_request_time.append(
            session.query(RealOrder).filter_by(candidate_id=cid).count()
        )
        return httpx.Response(
            200,
            json={
                "rt_cd": "0",
                "msg1": "ok",
                "output": {"ODNO": "ANCHOR-INT-99"},
            },
        )

    transport = _build_transport(handler, settings)
    executor = RealOrderExecutor(transport=transport)
    executor.execute(session, candidate_id=cid, settings=settings)

    assert rows_at_request_time == [1]


# ---------------------------------------------------------------------------
# 7. Duplicate guard — a SUBMITTED real order blocks a second attempt
# ---------------------------------------------------------------------------


def test_int_real_path_duplicate_blocks_second_attempt(session):
    cid = _seed_candidate(session)
    settings = _make_real_settings()
    captured = {"reqs": 0}

    def handler(request):
        captured["reqs"] += 1
        return httpx.Response(
            200,
            json={"rt_cd": "0", "msg1": "ok", "output": {"ODNO": "DUP-INT-1"}},
        )

    transport = _build_transport(handler, settings)
    executor = RealOrderExecutor(transport=transport)

    first = executor.execute(session, candidate_id=cid, settings=settings)
    session.commit()
    assert first.success is True

    second = executor.execute(session, candidate_id=cid, settings=settings)
    assert second.blocked_reason == "DUPLICATE_REAL_ORDER"
    # Transport must NOT have been re-invoked.
    assert captured["reqs"] == 1


# ---------------------------------------------------------------------------
# 8. dry-run / real path co-existence in the same DB
# ---------------------------------------------------------------------------


def test_int_dry_run_then_real_path_on_separate_candidates(session):
    """Two candidates: one runs dry-run, one runs real. Both succeed end-to-end."""
    cid_dry = _seed_candidate(session)

    # Look up the account_id of the just-seeded candidate so we can attach a
    # second candidate to the same account.
    cand_repo = OrderCandidateRepository(session)
    first_cand = cand_repo.get_by_id(cid_dry)
    assert first_cand is not None
    account_id = first_cand.account_id

    cand2 = cand_repo.create(
        account_id=account_id,
        source="MANUAL", symbol="000660", side="BUY", quantity=5,
        order_type="MARKET", estimated_amount=Decimal("100_000"),
    )
    cand_repo.update_status(cand2, new_status="RISK_CHECKING")
    cand_repo.update_status(cand2, new_status="PENDING_APPROVAL")
    cand_repo.update_status(cand2, new_status="APPROVED")
    session.commit()

    # Run dry-run on cid_dry
    dry_executor = RealOrderExecutor()
    dry_result = dry_executor.execute(
        session, candidate_id=cid_dry,
        settings=_make_real_settings(real_order_dry_run=True),
    )
    session.commit()
    assert dry_result.dry_run is True
    assert dry_result.status == "DRY_RUN"

    # Run real on cand2 with respx-mocked transport.
    settings = _make_real_settings()

    def handler(request):
        return httpx.Response(
            200,
            json={"rt_cd": "0", "msg1": "ok", "output": {"ODNO": "MIXED-OK"}},
        )

    transport = _build_transport(handler, settings)
    real_executor = RealOrderExecutor(transport=transport)
    real_result = real_executor.execute(
        session, candidate_id=cand2.id, settings=settings
    )
    session.commit()
    assert real_result.dry_run is False
    assert real_result.status == "SUBMITTED"

    # DB has both: one DRY_RUN row, one SUBMITTED row.
    repo = RealOrderRepository(session)
    statuses = sorted(o.status for o in repo.list_recent())
    assert statuses == ["DRY_RUN", "SUBMITTED"]
