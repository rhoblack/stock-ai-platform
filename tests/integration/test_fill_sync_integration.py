"""Integration tests for v1.0 Phase D — FillSyncService + HttpxKisOrderTransport.

End-to-end verification that the FillSyncService delta-based idempotent
update plays nicely with the v1.0 Phase B real transport when fed
respx-style mock HTTP responses. ZERO real KIS calls.

Hard guarantees verified
------------------------
* Outbound HTTP = 0 (httpx.MockTransport intercepts every call).
* Repeat sync on the same upstream KIS state does NOT duplicate RealFill
  rows.
* PARTIAL → FULL across two syncs creates exactly two fills with
  quantities summing to the total.
* Negative-delta anomaly is detected and audited end-to-end.
* Plaintext order_no never appears in DB rows or audit details.
"""

from __future__ import annotations

from decimal import Decimal

import httpx
import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.pool import StaticPool

from app.broker.fill_sync_service import FillSyncService
from app.broker.kis_order_transport_real import HttpxKisOrderTransport
from app.config.settings import Settings
from app.data.repositories.approval_audit_log import ApprovalAuditLogRepository
from app.data.repositories.order_candidate import OrderCandidateRepository
from app.data.repositories.real_fill import RealFillRepository
from app.data.repositories.real_order import RealOrderRepository
from app.data.repositories.virtual_account import VirtualAccountRepository
from app.db.base import Base
from app.db.models import RealOrder
from app.db.session import create_session_factory


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


def _real_settings(**overrides) -> Settings:
    base = dict(
        kis_account_no="000000000012",
        kis_app_key="test-app-key",
        kis_app_secret="test-app-secret",
    )
    base.update(overrides)
    return Settings(**base)


def _seed_real_order(
    session,
    *,
    status: str = "SUBMITTED",
    quantity: int = 10,
    estimated_amount: Decimal = Decimal("1_000_000"),
) -> int:
    acc = VirtualAccountRepository(session).create(
        name="int-fill-sync", initial_cash=Decimal("10_000_000")
    )
    session.flush()

    cand_repo = OrderCandidateRepository(session)
    cand = cand_repo.create(
        account_id=acc.id, source="MANUAL", symbol="005930", side="BUY",
        quantity=quantity, order_type="MARKET",
        estimated_amount=estimated_amount,
    )
    cand_repo.update_status(cand, new_status="RISK_CHECKING")
    cand_repo.update_status(cand, new_status="PENDING_APPROVAL")
    cand_repo.update_status(cand, new_status="APPROVED")
    session.flush()

    order = RealOrderRepository(session).create(
        candidate_id=cand.id, symbol="005930", side="BUY",
        quantity=quantity, order_type="MARKET",
        estimated_amount=estimated_amount,
        status=status, dry_run=(status == "DRY_RUN"),
        fake_order_no=None,
    )
    session.commit()
    return order.id


def _build_real_transport(handler) -> HttpxKisOrderTransport:
    settings = _real_settings()
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
        access_token="test-token",
        account_no=settings.kis_account_no,
    )


# ---------------------------------------------------------------------------
# 1. FULL fill — end-to-end via HttpxKisOrderTransport (mock HTTP)
# ---------------------------------------------------------------------------


def test_int_fill_sync_full_end_to_end(session):
    cid = _seed_real_order(session, status="SUBMITTED", quantity=10)
    captured = {"calls": 0}

    def handler(request):
        captured["calls"] += 1
        return httpx.Response(
            200,
            json={
                "rt_cd": "0",
                "msg1": "조회 성공",
                "output1": [
                    {
                        "ord_qty": "10",
                        "tot_ccld_qty": "10",
                        "cncl_yn": "N",
                        "rjct_yn": "N",
                    }
                ],
            },
        )

    svc = FillSyncService(transport=_build_real_transport(handler))
    result = svc.sync_fills(
        session, cid, kis_order_no_plaintext="REAL-ORD-INT-001"
    )
    session.commit()

    assert captured["calls"] == 1
    assert result.fill_status == "FULL"
    assert result.delta == 10
    assert result.created_fill_count == 1

    fills = RealFillRepository(session).list_by_order(cid)
    assert len(fills) == 1
    assert fills[0].quantity == 10

    refreshed = session.get(RealOrder, cid)
    assert refreshed.status == "FILLED"


# ---------------------------------------------------------------------------
# 2. PARTIAL → FULL across two syncs appends only the delta
# ---------------------------------------------------------------------------


def test_int_fill_sync_partial_then_full_appends_delta(session):
    cid = _seed_real_order(session, status="SUBMITTED", quantity=10)
    state = {"phase": 0}

    def handler(request):
        state["phase"] += 1
        if state["phase"] == 1:
            # First sync: 4/10 partially filled
            return httpx.Response(
                200,
                json={
                    "rt_cd": "0",
                    "msg1": "ok",
                    "output1": [{
                        "ord_qty": "10", "tot_ccld_qty": "4",
                        "cncl_yn": "N", "rjct_yn": "N",
                    }],
                },
            )
        # Second sync: 10/10 fully filled
        return httpx.Response(
            200,
            json={
                "rt_cd": "0",
                "msg1": "ok",
                "output1": [{
                    "ord_qty": "10", "tot_ccld_qty": "10",
                    "cncl_yn": "N", "rjct_yn": "N",
                }],
            },
        )

    svc = FillSyncService(transport=_build_real_transport(handler))
    r1 = svc.sync_fills(session, cid, kis_order_no_plaintext="REAL-ORD-002")
    session.commit()
    r2 = svc.sync_fills(session, cid, kis_order_no_plaintext="REAL-ORD-002")
    session.commit()

    assert r1.fill_status == "PARTIAL" and r1.delta == 4
    assert r2.fill_status == "FULL" and r2.delta == 6

    fills = RealFillRepository(session).list_by_order(cid)
    assert sorted(f.quantity for f in fills) == [4, 6]


# ---------------------------------------------------------------------------
# 3. Repeat sync on identical KIS state → idempotent (no duplicate rows)
# ---------------------------------------------------------------------------


def test_int_fill_sync_repeat_same_state_idempotent(session):
    cid = _seed_real_order(session, status="SUBMITTED", quantity=10)

    def handler(request):
        return httpx.Response(
            200,
            json={
                "rt_cd": "0",
                "msg1": "ok",
                "output1": [{
                    "ord_qty": "10", "tot_ccld_qty": "5",
                    "cncl_yn": "N", "rjct_yn": "N",
                }],
            },
        )

    svc = FillSyncService(transport=_build_real_transport(handler))
    svc.sync_fills(session, cid, kis_order_no_plaintext="X")
    session.commit()
    r2 = svc.sync_fills(session, cid, kis_order_no_plaintext="X")
    session.commit()

    assert r2.fill_status == "PARTIAL"
    assert r2.delta == 0
    assert r2.created_fill_count == 0

    fills = RealFillRepository(session).list_by_order(cid)
    assert len(fills) == 1


# ---------------------------------------------------------------------------
# 4. Negative-delta anomaly end-to-end
# ---------------------------------------------------------------------------


def test_int_fill_sync_negative_delta_writes_audit(session):
    cid = _seed_real_order(session, status="SUBMITTED", quantity=10)
    state = {"phase": 0}

    def handler(request):
        state["phase"] += 1
        filled = "8" if state["phase"] == 1 else "3"
        return httpx.Response(
            200,
            json={
                "rt_cd": "0",
                "msg1": "ok",
                "output1": [{
                    "ord_qty": "10", "tot_ccld_qty": filled,
                    "cncl_yn": "N", "rjct_yn": "N",
                }],
            },
        )

    svc = FillSyncService(transport=_build_real_transport(handler))
    svc.sync_fills(session, cid, kis_order_no_plaintext="X")
    session.commit()
    r2 = svc.sync_fills(session, cid, kis_order_no_plaintext="X")
    session.commit()

    assert r2.fill_status == "FAILED"
    assert r2.delta == -5

    audit_repo = ApprovalAuditLogRepository(session)
    order = session.get(RealOrder, cid)
    rows = [
        r for r in audit_repo.list_by_candidate(order.candidate_id)
        if r.event_type == "FILL_SYNC_NEGATIVE_DELTA"
    ]
    assert len(rows) == 1


# ---------------------------------------------------------------------------
# 5. Transport failure (HTTP 503) classified as FAILED + audit
# ---------------------------------------------------------------------------


def test_int_fill_sync_5xx_marks_failed_and_audits(session):
    cid = _seed_real_order(session, status="SUBMITTED", quantity=10)

    def handler(request):
        return httpx.Response(503, text="service unavailable")

    svc = FillSyncService(transport=_build_real_transport(handler))
    result = svc.sync_fills(session, cid, kis_order_no_plaintext="X")
    session.commit()

    assert result.fill_status == "FAILED"
    audit_repo = ApprovalAuditLogRepository(session)
    order = session.get(RealOrder, cid)
    rows = [
        r for r in audit_repo.list_by_candidate(order.candidate_id)
        if r.event_type == "REAL_ORDER_FILL_FAILED"
    ]
    assert len(rows) == 1


# ---------------------------------------------------------------------------
# 6. Plaintext order_no never persisted by the integration chain
# ---------------------------------------------------------------------------


def test_int_fill_sync_plaintext_never_persisted(session):
    cid = _seed_real_order(session, status="SUBMITTED", quantity=10)
    plaintext = "PLAINTEXT-INT-SECRET-99999"

    def handler(request):
        return httpx.Response(
            200,
            json={
                "rt_cd": "0",
                "msg1": "ok",
                "output1": [{
                    "ord_qty": "10", "tot_ccld_qty": "10",
                    "cncl_yn": "N", "rjct_yn": "N",
                }],
            },
        )

    svc = FillSyncService(transport=_build_real_transport(handler))
    svc.sync_fills(session, cid, kis_order_no_plaintext=plaintext)
    session.commit()

    # Scan EVERY persisted row for the plaintext.
    fills = RealFillRepository(session).list_by_order(cid)
    for f in fills:
        for col in (f.symbol, f.side, f.fill_status):
            assert plaintext not in str(col)
        assert plaintext not in str(f.fill_price)
        assert plaintext not in str(f.gross_amount)

    audit_repo = ApprovalAuditLogRepository(session)
    order = session.get(RealOrder, cid)
    for row in audit_repo.list_by_candidate(order.candidate_id):
        assert plaintext not in str(row.reason or "")
        assert plaintext not in str(row.details_json or {})


# ---------------------------------------------------------------------------
# 7. CANCELED transition end-to-end
# ---------------------------------------------------------------------------


def test_int_fill_sync_canceled_transitions_status(session):
    cid = _seed_real_order(session, status="SUBMITTED", quantity=10)

    def handler(request):
        return httpx.Response(
            200,
            json={
                "rt_cd": "0",
                "msg1": "ok",
                "output1": [{
                    "ord_qty": "10", "tot_ccld_qty": "0",
                    "cncl_yn": "Y", "rjct_yn": "N",
                }],
            },
        )

    svc = FillSyncService(transport=_build_real_transport(handler))
    result = svc.sync_fills(session, cid, kis_order_no_plaintext="X")
    session.commit()

    assert result.fill_status == "CANCELED"
    refreshed = session.get(RealOrder, cid)
    assert refreshed.status == "CANCELED"
    assert RealFillRepository(session).list_by_order(cid) == []
