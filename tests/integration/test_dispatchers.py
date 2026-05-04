from datetime import date, datetime, timezone
from decimal import Decimal

import httpx
import pytest
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool

from app.config.settings import Settings
from app.data.repositories import (
    DataSnapshotRepository,
    HoldingCheckRepository,
    JobRunRepository,
    NotificationLogRepository,
    RecommendationRepository,
    RecommendationRunRepository,
)
from app.db import Base
from app.db.models import (
    DataSnapshot,
    HoldingCheck,
    JobRun,
    Recommendation,
    RecommendationRun,
)
from app.db.session import create_session_factory
from app.notification.dispatchers import (
    HoldingCheckReportDispatcher,
    RecommendationReportDispatcher,
    HoldingRiskAlertDispatcher,
)
from app.notification.notification_service import (
    MESSAGE_TYPE_REPORT,
    NotificationService,
)
from app.notification.report_generator import ReportGenerator
from app.notification.telegram_notifier import TelegramNotifier


@pytest.fixture()
def session():
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )
    Base.metadata.create_all(engine)
    factory = create_session_factory(engine)
    s = factory()
    try:
        yield s
    finally:
        s.close()
        Base.metadata.drop_all(engine)


def _settings(**overrides) -> Settings:
    defaults = {
        "telegram_enabled": False,
        "telegram_bot_token": "fake_test_token",
        "telegram_chat_id": "1234567890",
        "telegram_api_base_url": "https://mock-telegram.local",
        "telegram_timeout_seconds": 5,
    }
    defaults.update(overrides)
    return Settings(**defaults)


def _notifier(settings: Settings, handler=None) -> TelegramNotifier:
    if handler is None:
        return TelegramNotifier(settings=settings)
    return TelegramNotifier(
        settings=settings,
        http_client=httpx.Client(
            transport=httpx.MockTransport(handler),
            base_url=settings.telegram_api_base_url,
        ),
    )


def _build_recommendation_dispatcher(session, notifier):
    return RecommendationReportDispatcher(
        report_generator=ReportGenerator(),
        notification_service=NotificationService(
            notifier=notifier,
            log_repository=NotificationLogRepository(session),
        ),
        run_repository=RecommendationRunRepository(session),
        recommendation_repository=RecommendationRepository(session),
        snapshot_repository=DataSnapshotRepository(session),
    )


def _build_holding_check_dispatcher(session, notifier):
    return HoldingCheckReportDispatcher(
        report_generator=ReportGenerator(),
        notification_service=NotificationService(
            notifier=notifier,
            log_repository=NotificationLogRepository(session),
        ),
        holding_check_repository=HoldingCheckRepository(session),
        snapshot_repository=DataSnapshotRepository(session),
    )


# ---------- recommendation seeding ----------

def _seed_recommendation_run(session) -> tuple[int, int]:
    snapshot = DataSnapshotRepository(session).add(
        DataSnapshot(
            snapshot_time=datetime(2026, 5, 4, 6, 0, tzinfo=timezone.utc),
            symbol="005930",
            snapshot_type="RECOMMENDATION",
            indicator_data_json={"technical_score": "82"},
            market_context_json={
                "phase": "5-3",
                "risk_summary": {
                    "level": "LOW",
                    "flags": [],
                    "penalty": "0.0000",
                },
            },
        ),
    )
    run = RecommendationRunRepository(session).add(
        RecommendationRun(
            run_date=date(2026, 5, 4),
            started_at=datetime(2026, 5, 4, 6, 0, tzinfo=timezone.utc),
            finished_at=datetime(2026, 5, 4, 6, 1, tzinfo=timezone.utc),
            status="SUCCESS",
            telegram_sent=False,
            market_summary={
                "universe": "MARKET_CAP_TOP_500",
                "candidate_count": 1,
                "saved_count": 1,
                "phase": "5-3",
            },
        ),
    )
    session.flush()
    RecommendationRepository(session).add(
        Recommendation(
            run_id=run.run_id,
            rank=1,
            market="KOSPI",
            symbol="005930",
            name="삼성전자",
            grade="A",
            total_score=Decimal("82"),
            technical_score=Decimal("82"),
            risk_score=Decimal("0.0000"),
            reason="관찰 후보 · 기술점수 82",
            risk_note="Phase 5-3 placeholder",
            snapshot_id=snapshot.snapshot_id,
        ),
    )
    session.flush()
    session.commit()
    return run.run_id, snapshot.snapshot_id


def _seed_holding_check(session, *, level: str, flags: list[str]) -> int:
    snapshot = DataSnapshotRepository(session).add(
        DataSnapshot(
            snapshot_time=datetime(2026, 5, 4, 8, 30, tzinfo=timezone.utc),
            symbol="005930",
            snapshot_type="HOLDING_CHECK",
            market_context_json={
                "check_date": "2026-05-04",
                "check_type": "PRE_MARKET",
                "phase": "5-3",
                "risk_summary": {
                    "level": level,
                    "flags": flags,
                    "penalty": "23.0000",
                },
            },
        ),
    )
    HoldingCheckRepository(session).add(
        HoldingCheck(
            check_date=date(2026, 5, 4),
            check_type="PRE_MARKET",
            symbol="005930",
            current_price=Decimal("65000"),
            avg_buy_price=Decimal("70000"),
            return_rate=Decimal("-7.1429"),
            total_score=Decimal("0"),
            grade="D",
            decision="SELL_REVIEW",
            reason="매도 검토",
            alert=True,
            snapshot_id=snapshot.snapshot_id,
        ),
    )
    session.commit()
    return snapshot.snapshot_id


# ---------- RecommendationReportDispatcher ----------

def test_recommendation_dispatcher_dry_run_records_log_without_setting_flag(session):
    run_id, _ = _seed_recommendation_run(session)
    notifier = _notifier(_settings(telegram_enabled=False))
    dispatcher = _build_recommendation_dispatcher(session, notifier)

    outcome = dispatcher.dispatch(run_id=run_id)
    session.commit()

    assert outcome.run_id == run_id
    assert outcome.recommendation_count == 1
    assert outcome.notification.status == "DRY_RUN"
    assert outcome.notification.sent is False
    assert outcome.telegram_sent_flag_updated is False
    assert "[AI 주식 리포트] 2026-05-04" in outcome.message_text
    assert "삼성전자 (005930)" in outcome.message_text
    assert "리스크: LOW" in outcome.message_text

    # notification_logs row written even on DRY_RUN
    log = NotificationLogRepository(session).list()[0]
    assert log.status == "DRY_RUN"
    assert log.message_type == MESSAGE_TYPE_REPORT
    assert log.sent_at is None

    run = RecommendationRunRepository(session).get(run_id)
    assert run.telegram_sent is False  # not flipped on DRY_RUN


def test_recommendation_dispatcher_success_path_marks_telegram_sent(session):
    run_id, _ = _seed_recommendation_run(session)

    def handler(request):
        return httpx.Response(200, json={"ok": True, "result": {"message_id": 7}})

    notifier = _notifier(_settings(telegram_enabled=True), handler)
    dispatcher = _build_recommendation_dispatcher(session, notifier)

    outcome = dispatcher.dispatch(run_id=run_id)
    session.commit()

    assert outcome.notification.status == "SUCCESS"
    assert outcome.notification.sent is True
    assert outcome.telegram_sent_flag_updated is True

    run = RecommendationRunRepository(session).get(run_id)
    assert run.telegram_sent is True


def test_recommendation_dispatcher_failed_send_does_not_set_telegram_sent(session):
    run_id, _ = _seed_recommendation_run(session)

    def handler(request):
        return httpx.Response(200, json={"ok": False, "description": "chat not found"})

    notifier = _notifier(_settings(telegram_enabled=True), handler)
    dispatcher = _build_recommendation_dispatcher(session, notifier)

    outcome = dispatcher.dispatch(run_id=run_id)
    session.commit()

    assert outcome.notification.status == "FAILED"
    assert outcome.telegram_sent_flag_updated is False
    run = RecommendationRunRepository(session).get(run_id)
    assert run.telegram_sent is False


def test_recommendation_dispatcher_unknown_run_id_raises(session):
    notifier = _notifier(_settings())
    dispatcher = _build_recommendation_dispatcher(session, notifier)
    with pytest.raises(ValueError):
        dispatcher.dispatch(run_id=9999)


def test_recommendation_dispatcher_links_related_job_id(session):
    run_id, _ = _seed_recommendation_run(session)
    job = JobRunRepository(session).add(
        JobRun(
            job_name="send_recommendation_report",
            started_at=datetime(2026, 5, 4, 6, 0),
            status="RUNNING",
        ),
    )
    session.commit()

    notifier = _notifier(_settings())
    dispatcher = _build_recommendation_dispatcher(session, notifier)
    dispatcher.dispatch(run_id=run_id, related_job_id=job.job_id)
    session.commit()

    log = NotificationLogRepository(session).list()[0]
    assert log.related_job_id == job.job_id


def test_recommendation_dispatcher_handles_run_with_no_recommendations(session):
    run = RecommendationRunRepository(session).add(
        RecommendationRun(
            run_date=date(2026, 5, 4),
            started_at=datetime(2026, 5, 4, 6, 0),
            status="EMPTY",
            telegram_sent=False,
            market_summary={"universe": "MARKET_CAP_TOP_500"},
        ),
    )
    session.commit()

    notifier = _notifier(_settings())
    dispatcher = _build_recommendation_dispatcher(session, notifier)
    outcome = dispatcher.dispatch(run_id=run.run_id)
    session.commit()

    assert outcome.recommendation_count == 0
    assert "관찰 후보가 없습니다" in outcome.message_text
    assert outcome.notification.status == "DRY_RUN"


# ---------- HoldingCheckReportDispatcher ----------

def test_holding_dispatcher_dry_run_with_high_risk_check(session):
    _seed_holding_check(session, level="HIGH", flags=["MA20_BREAKDOWN", "STOP_LOSS_NEAR"])
    notifier = _notifier(_settings(telegram_enabled=False))
    dispatcher = _build_holding_check_dispatcher(session, notifier)

    outcome = dispatcher.dispatch(
        check_date=date(2026, 5, 4),
        check_type="PRE_MARKET",
    )
    session.commit()

    assert outcome.holding_check_count == 1
    assert outcome.check_type == "PRE_MARKET"
    assert "[보유 종목 장전 점검] 2026-05-04" in outcome.message_text
    assert "⚠ 위험 경고 종목 (1건)" in outcome.message_text
    assert "20일선 이탈" in outcome.message_text
    assert "손절 근접" in outcome.message_text
    assert outcome.notification.status == "DRY_RUN"
    assert outcome.notification.sent is False

    log = NotificationLogRepository(session).list()[0]
    assert log.status == "DRY_RUN"
    assert log.message_type == MESSAGE_TYPE_REPORT


def test_holding_dispatcher_post_market_uses_post_market_title(session):
    snapshot = DataSnapshotRepository(session).add(
        DataSnapshot(
            snapshot_time=datetime(2026, 5, 4, 16, 30, tzinfo=timezone.utc),
            symbol="005930",
            snapshot_type="HOLDING_CHECK",
            market_context_json={
                "risk_summary": {"level": "LOW", "flags": [], "penalty": "0"},
            },
        ),
    )
    HoldingCheckRepository(session).add(
        HoldingCheck(
            check_date=date(2026, 5, 4),
            check_type="POST_MARKET",
            symbol="005930",
            current_price=Decimal("70000"),
            avg_buy_price=Decimal("70000"),
            return_rate=Decimal("0"),
            total_score=Decimal("28"),
            grade="D",
            decision="SELL_REVIEW",
            reason="reason",
            alert=False,
            snapshot_id=snapshot.snapshot_id,
        ),
    )
    session.commit()

    notifier = _notifier(_settings())
    dispatcher = _build_holding_check_dispatcher(session, notifier)
    outcome = dispatcher.dispatch(
        check_date=date(2026, 5, 4),
        check_type="POST_MARKET",
    )
    assert "[보유 종목 장후 점검]" in outcome.message_text
    assert outcome.holding_check_count == 1


def test_holding_dispatcher_with_no_checks_sends_empty_message(session):
    notifier = _notifier(_settings())
    dispatcher = _build_holding_check_dispatcher(session, notifier)
    outcome = dispatcher.dispatch(
        check_date=date(2026, 5, 4),
        check_type="PRE_MARKET",
    )
    session.commit()

    assert outcome.holding_check_count == 0
    assert "점검 대상 보유 종목이 없습니다" in outcome.message_text
    assert NotificationLogRepository(session).list()[0].status == "DRY_RUN"


def test_holding_dispatcher_rejects_invalid_check_type(session):
    notifier = _notifier(_settings())
    dispatcher = _build_holding_check_dispatcher(session, notifier)
    with pytest.raises(ValueError):
        dispatcher.dispatch(
            check_date=date(2026, 5, 4),
            check_type="MIDDAY",
        )


def test_holding_dispatcher_success_path_records_sent_at(session):
    _seed_holding_check(session, level="LOW", flags=[])

    def handler(request):
        return httpx.Response(200, json={"ok": True, "result": {"message_id": 11}})

    notifier = _notifier(_settings(telegram_enabled=True), handler)
    dispatcher = _build_holding_check_dispatcher(session, notifier)
    outcome = dispatcher.dispatch(
        check_date=date(2026, 5, 4),
        check_type="PRE_MARKET",
    )
    session.commit()

    assert outcome.notification.status == "SUCCESS"
    assert outcome.notification.sent is True
    log = NotificationLogRepository(session).list()[0]
    assert log.status == "SUCCESS"
    assert log.sent_at is not None

# ---------- HoldingRiskAlertDispatcher ----------

def test_holding_risk_alert_dispatcher_dedup(session):
    _seed_holding_check(session, level="HIGH", flags=["MA20_BREAKDOWN"])
    notifier = _notifier(_settings(telegram_enabled=False))
    dispatcher = _build_holding_risk_alert_dispatcher(session, notifier)

    # 1. 최초 발송 (경고 조건 만족하므로 1건이 발송되어야 함)
    sent_count = dispatcher.dispatch(
        check_date=date(2026, 5, 4),
        check_type="PRE_MARKET",
    )
    session.commit()
    assert sent_count == 1

    logs = [log for log in NotificationLogRepository(session).list() if log.message_type == "ALERT"]
    assert len(logs) == 1
    assert logs[0].target == "ALERT_HOLDING:005930:2026-05-04:PRE_MARKET"

    # 2. 2차 발송 시도 (동일한 조건이므로 dedup 정책에 의해 0건이 발송되어야 함)
    sent_count_retry = dispatcher.dispatch(
        check_date=date(2026, 5, 4),
        check_type="PRE_MARKET",
    )
    assert sent_count_retry == 0
