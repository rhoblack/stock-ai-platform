from datetime import date, datetime, timezone
from decimal import Decimal

import pytest
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool

from app.config.settings import Settings
from app.data.repositories import (
    DailyPriceRepository,
    HoldingCheckRepository,
    HoldingRepository,
    JobRunRepository,
    NotificationLogRepository,
    RecommendationRepository,
    RecommendationRunRepository,
    StockIndicatorRepository,
    StockUniverseMemberRepository,
    StockUniverseRepository,
)
from app.db import Base
from app.db.models import (
    Holding,
    Recommendation,
    RecommendationRun,
    StockUniverse,
    StockUniverseMember,
)
from app.db.session import create_session_factory
from app.scheduler.jobs import (
    JOB_FUNCTIONS,
    JOB_NAME_CALCULATE_INDICATORS,
    JOB_NAME_COLLECT_MARKET_CLOSE,
    JOB_NAME_POST_MARKET_HOLDING_CHECK,
    JOB_NAME_PRE_MARKET_HOLDING_CHECK,
    JOB_NAME_SEND_RECOMMENDATION_REPORT,
    JOB_NAME_UPDATE_RECOMMENDATION_RESULTS,
    JOB_STATUS_FAILED,
    JOB_STATUS_PARTIAL,
    JOB_STATUS_SUCCESS,
    JobResult,
    calculate_technical_indicators,
    collect_market_close_data,
    run_job,
    run_post_market_holding_check,
    run_pre_market_holding_check,
    send_recommendation_report,
    update_recommendation_results,
)


@pytest.fixture()
def session_factory():
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )
    Base.metadata.create_all(engine)
    factory = create_session_factory(engine)
    yield factory
    Base.metadata.drop_all(engine)


def _dry_run_settings() -> Settings:
    return Settings(
        telegram_enabled=False,
        telegram_bot_token="fake_test_token",
        telegram_chat_id="1234567890",
        telegram_api_base_url="https://mock-telegram.local",
        telegram_timeout_seconds=5,
    )


def _open_session(session_factory):
    """Open a session and pre-populate dry-run telegram settings on session.info.

    Jobs read ``session.info['settings']`` first so tests don't depend on env
    or the lru_cached ``get_settings``.
    """
    session = session_factory()
    session.info["settings"] = _dry_run_settings()
    return session


def _read_session(session_factory):
    """Convenience for assertions: opens a fresh session against the same engine."""
    return session_factory()


# ---------- run_job wrapper ----------

def test_run_job_records_success_with_summary(session_factory):
    def fn(session):
        return JobResult(
            status=JOB_STATUS_SUCCESS,
            summary={"saved": 7, "phase": "test"},
        )

    outcome = run_job(
        session_factory=session_factory,
        job_name="custom_test_job",
        fn=fn,
    )

    assert outcome.status == JOB_STATUS_SUCCESS
    assert outcome.result_summary == {"saved": 7, "phase": "test"}
    assert outcome.error_message is None
    assert outcome.finished_at >= outcome.started_at

    session = _read_session(session_factory)
    try:
        rows = JobRunRepository(session).list()
        assert len(rows) == 1
        row = rows[0]
        assert row.job_id == outcome.job_run_id
        assert row.job_name == "custom_test_job"
        assert row.status == JOB_STATUS_SUCCESS
        assert row.finished_at is not None
        assert row.result_summary == {"saved": 7, "phase": "test"}
        assert row.error_message is None
    finally:
        session.close()


def test_run_job_records_partial_status(session_factory):
    def fn(session):
        return JobResult(
            status=JOB_STATUS_PARTIAL,
            summary={"saved": 2, "missed": 3},
            error_message="news collection failed",
        )

    outcome = run_job(
        session_factory=session_factory,
        job_name="partial_job",
        fn=fn,
    )

    assert outcome.status == JOB_STATUS_PARTIAL
    assert outcome.error_message == "news collection failed"

    session = _read_session(session_factory)
    try:
        row = JobRunRepository(session).list()[0]
        assert row.status == JOB_STATUS_PARTIAL
        assert row.error_message == "news collection failed"
        assert row.result_summary == {"saved": 2, "missed": 3}
    finally:
        session.close()


def test_run_job_catches_exception_and_records_failed(session_factory):
    def fn(session):
        raise RuntimeError("boom")

    outcome = run_job(
        session_factory=session_factory,
        job_name="failing_job",
        fn=fn,
    )

    assert outcome.status == JOB_STATUS_FAILED
    assert outcome.result_summary is None
    assert "RuntimeError" in outcome.error_message
    assert "boom" in outcome.error_message

    session = _read_session(session_factory)
    try:
        row = JobRunRepository(session).list()[0]
        assert row.status == JOB_STATUS_FAILED
        assert row.finished_at is not None
        assert "RuntimeError" in row.error_message
    finally:
        session.close()


def test_run_job_failure_does_not_persist_partial_writes(session_factory):
    """If fn writes rows then raises, the wrapper rolls back the work session."""

    def fn(session):
        # Write a holding that should be rolled back
        HoldingRepository(session).add(
            Holding(
                symbol="ROLLBK",
                quantity=Decimal("1"),
                avg_buy_price=Decimal("100"),
                is_active=True,
            ),
        )
        raise RuntimeError("boom after partial write")

    run_job(
        session_factory=session_factory,
        job_name="partial_write_then_fail",
        fn=fn,
    )

    session = _read_session(session_factory)
    try:
        # Job log row IS persisted
        assert len(JobRunRepository(session).list()) == 1
        # Partial write was rolled back
        assert HoldingRepository(session).get_active_by_symbol("ROLLBK") is None
    finally:
        session.close()


def test_run_job_success_persists_work_session_writes(session_factory):
    def fn(session):
        HoldingRepository(session).add(
            Holding(
                symbol="KEEP01",
                quantity=Decimal("5"),
                avg_buy_price=Decimal("200"),
                is_active=True,
            ),
        )
        return JobResult(summary={"added": 1})

    run_job(
        session_factory=session_factory,
        job_name="success_writes",
        fn=fn,
    )

    session = _read_session(session_factory)
    try:
        assert (
            HoldingRepository(session).get_active_by_symbol("KEEP01") is not None
        )
    finally:
        session.close()


def test_run_job_returns_unique_job_run_ids(session_factory):
    def fn(session):
        return JobResult(summary={})

    outcome_a = run_job(session_factory=session_factory, job_name="a", fn=fn)
    outcome_b = run_job(session_factory=session_factory, job_name="b", fn=fn)
    assert outcome_a.job_run_id != outcome_b.job_run_id


# ---------- collect_market_close_data ----------

def test_collect_market_close_data_returns_placeholder(session_factory):
    session = session_factory()
    try:
        result = collect_market_close_data(session)
    finally:
        session.close()

    assert result.status == JOB_STATUS_SUCCESS
    assert result.summary["placeholder"] is True
    assert result.summary["phase"] == "8"


# ---------- calculate_technical_indicators ----------

def test_calculate_technical_indicators_skips_when_universe_missing(session_factory):
    session = session_factory()
    try:
        result = calculate_technical_indicators(session)
    finally:
        session.close()

    assert result.status == JOB_STATUS_SUCCESS
    assert result.summary["skipped"] is True
    assert result.summary["snapshots_saved"] == 0


def test_calculate_technical_indicators_runs_indicator_service(session_factory):
    session = session_factory()
    try:
        universe = StockUniverseRepository(session).add(
            StockUniverse(name="MARKET_CAP_TOP_500"),
        )
        session.flush()
        StockUniverseMemberRepository(session).add(
            StockUniverseMember(universe_id=universe.universe_id, symbol="005930"),
        )
        # Seed a small price history (insufficient for MA60+, sufficient to
        # produce an IndicatorSnapshot row with technical_score=0)
        for offset in range(5):
            DailyPriceRepository(session).upsert(
                symbol="005930",
                price_date=date(2026, 5, 1 + offset),
                open_price=Decimal("100"),
                high_price=Decimal("100"),
                low_price=Decimal("100"),
                close_price=Decimal("100"),
                volume=1_000_000,
            )
        session.commit()

        result = calculate_technical_indicators(session)
        session.commit()
    finally:
        session.close()

    assert result.status == JOB_STATUS_SUCCESS
    assert result.summary["members_count"] == 1
    assert result.summary["snapshots_saved"] == 1
    assert result.summary["skipped_no_prices"] == 0

    session2 = _read_session(session_factory)
    try:
        indicator = StockIndicatorRepository(session2).get_latest_by_symbol("005930")
        assert indicator is not None
    finally:
        session2.close()


# ---------- send_recommendation_report ----------

def test_send_recommendation_report_partial_when_no_universe(session_factory):
    session = _open_session(session_factory)
    try:
        result = send_recommendation_report(session)
        session.commit()
    finally:
        session.close()

    assert result.status == JOB_STATUS_PARTIAL
    assert result.summary["engine_status"] == "EMPTY"
    assert result.summary["telegram_sent"] is False
    assert result.summary["saved_count"] == 0
    # Dispatcher still ran (DRY_RUN) and emitted an empty-candidates message.
    assert result.summary["notification_status"] == "DRY_RUN"
    assert result.summary["recommendation_count"] == 0
    assert result.summary["telegram_sent_flag_updated"] is False
    assert result.summary["message_length"] > 0

    session2 = _read_session(session_factory)
    try:
        logs = NotificationLogRepository(session2).list()
        assert len(logs) == 1
        assert logs[0].status == "DRY_RUN"
        assert logs[0].message_type == "REPORT"
    finally:
        session2.close()


def test_send_recommendation_report_success_with_seeded_universe(session_factory):
    session = _open_session(session_factory)
    try:
        universe = StockUniverseRepository(session).add(
            StockUniverse(name="MARKET_CAP_TOP_500"),
        )
        session.flush()
        StockUniverseMemberRepository(session).add(
            StockUniverseMember(universe_id=universe.universe_id, symbol="005930"),
        )
        from app.db.models import Stock

        session.add(Stock(symbol="005930", name="삼성전자", market="KOSPI"))
        StockIndicatorRepository(session).upsert(
            symbol="005930",
            indicator_date=date(2026, 5, 4),
            technical_score=Decimal("80"),
            ma_alignment="BULL",
            volume_ratio_20d=Decimal("1.5"),
        )
        session.commit()

        result = send_recommendation_report(session)
        session.commit()
    finally:
        session.close()

    assert result.status == JOB_STATUS_SUCCESS
    assert result.summary["engine_status"] == "SUCCESS"
    assert result.summary["telegram_sent"] is False
    assert result.summary["saved_count"] == 1
    assert result.summary["run_id"] is not None
    assert result.summary["recommendation_count"] == 1
    assert result.summary["notification_status"] == "DRY_RUN"
    assert result.summary["telegram_sent_flag_updated"] is False

    session2 = _read_session(session_factory)
    try:
        run = RecommendationRunRepository(session2).get(result.summary["run_id"])
        assert run is not None
        assert run.telegram_sent is False  # DRY_RUN does not set the flag
        assert RecommendationRepository(session2).list_by_run_id(run.run_id)
        log = NotificationLogRepository(session2).list()[0]
        assert log.status == "DRY_RUN"
    finally:
        session2.close()


# ---------- pre/post-market holding check ----------

def test_pre_market_holding_check_with_no_holdings(session_factory):
    session = _open_session(session_factory)
    try:
        result = run_pre_market_holding_check(session)
        session.commit()
    finally:
        session.close()

    assert result.status == JOB_STATUS_SUCCESS
    assert result.summary["check_type"] == "PRE_MARKET"
    assert result.summary["saved_count"] == 0
    assert result.summary["telegram_sent"] is False
    assert result.summary["notification_status"] == "DRY_RUN"
    assert result.summary["holding_check_count"] == 0
    assert result.summary["message_length"] > 0


def test_post_market_holding_check_processes_active_holdings(session_factory):
    session = _open_session(session_factory)
    try:
        HoldingRepository(session).add(
            Holding(
                symbol="005930",
                quantity=Decimal("10"),
                avg_buy_price=Decimal("100"),
                is_active=True,
            ),
        )
        DailyPriceRepository(session).upsert(
            symbol="005930",
            price_date=date(2026, 5, 4),
            open_price=Decimal("110"),
            high_price=Decimal("110"),
            low_price=Decimal("110"),
            close_price=Decimal("110"),
            volume=1_000_000,
        )
        StockIndicatorRepository(session).upsert(
            symbol="005930",
            indicator_date=date(2026, 5, 4),
            technical_score=Decimal("80"),
            ma20=Decimal("100"),
        )
        session.commit()

        result = run_post_market_holding_check(session)
        session.commit()
    finally:
        session.close()

    assert result.status == JOB_STATUS_SUCCESS
    assert result.summary["check_type"] == "POST_MARKET"
    assert result.summary["saved_count"] == 1
    assert result.summary["holding_check_count"] == 1
    assert result.summary["notification_status"] == "DRY_RUN"
    assert result.summary["telegram_sent"] is False

    session2 = _read_session(session_factory)
    try:
        checks = HoldingCheckRepository(session2).list_by_symbol("005930")
        assert len(checks) == 1
        assert checks[0].check_type == "POST_MARKET"
        log = NotificationLogRepository(session2).list()[0]
        assert log.status == "DRY_RUN"
    finally:
        session2.close()


# ---------- update_recommendation_results ----------

def test_update_recommendation_results_with_no_runs(session_factory):
    session = session_factory()
    try:
        result = update_recommendation_results(session)
        session.commit()
    finally:
        session.close()

    assert result.status == JOB_STATUS_SUCCESS
    assert result.summary["phase"] == "5-followup"
    assert result.summary["processed_runs"] == 0
    assert result.summary["processed_recommendations"] == 0
    assert result.summary["upserted_results"] == 0
    assert result.summary["pending_count"] == 0
    assert result.summary["success_count"] == 0
    assert result.summary["failed_count"] == 0


def test_update_recommendation_results_processes_seeded_run(session_factory):
    session = session_factory()
    rec_id: int
    try:
        run = RecommendationRunRepository(session).add(
            RecommendationRun(
                run_date=date(2026, 5, 4),
                started_at=datetime(2026, 5, 4, tzinfo=timezone.utc),
                status="SUCCESS",
                telegram_sent=False,
            ),
        )
        session.flush()
        rec = RecommendationRepository(session).add(
            Recommendation(
                run_id=run.run_id, rank=1, market="KOSPI",
                symbol="005930", name="삼성전자",
                grade="A", total_score=Decimal("80"),
            ),
        )
        DailyPriceRepository(session).upsert(
            symbol="005930", price_date=date(2026, 5, 4),
            open_price=Decimal("100"), high_price=Decimal("100"),
            low_price=Decimal("100"), close_price=Decimal("100"),
            volume=1_000_000,
        )
        DailyPriceRepository(session).upsert(
            symbol="005930", price_date=date(2026, 5, 5),
            open_price=Decimal("100"), high_price=Decimal("105"),
            low_price=Decimal("99"), close_price=Decimal("104"),
            volume=1_000_000,
        )
        session.commit()
        rec_id = rec.id

        result = update_recommendation_results(session)
        session.commit()
    finally:
        session.close()

    assert result.status == JOB_STATUS_SUCCESS
    assert result.summary["processed_recommendations"] == 1

    session2 = _read_session(session_factory)
    try:
        from app.data.repositories import RecommendationResultRepository

        rows = RecommendationResultRepository(session2).list_by_recommendation_id(rec_id)
        assert {r.days_after for r in rows} == {1, 3, 5, 20}
    finally:
        session2.close()


# ---------- registry sanity ----------

def test_job_functions_registry_covers_all_six_jobs():
    assert set(JOB_FUNCTIONS) == {
        JOB_NAME_COLLECT_MARKET_CLOSE,
        JOB_NAME_CALCULATE_INDICATORS,
        JOB_NAME_SEND_RECOMMENDATION_REPORT,
        JOB_NAME_PRE_MARKET_HOLDING_CHECK,
        JOB_NAME_POST_MARKET_HOLDING_CHECK,
        JOB_NAME_UPDATE_RECOMMENDATION_RESULTS,
    }


def test_run_job_with_registered_function(session_factory):
    """Smoke test: wrapper + registry can drive a registered job end-to-end."""
    outcome = run_job(
        session_factory=session_factory,
        job_name=JOB_NAME_COLLECT_MARKET_CLOSE,
        fn=JOB_FUNCTIONS[JOB_NAME_COLLECT_MARKET_CLOSE],
    )
    assert outcome.status == JOB_STATUS_SUCCESS
    assert outcome.result_summary["placeholder"] is True


def test_run_job_exposes_job_run_id_to_fn_via_session_info(session_factory):
    seen: dict = {}

    def fn(session):
        seen["job_run_id"] = session.info.get("job_run_id")
        return JobResult(summary={"ok": True})

    outcome = run_job(
        session_factory=session_factory,
        job_name="exposes_job_run_id",
        fn=fn,
    )
    assert seen["job_run_id"] == outcome.job_run_id


def test_send_recommendation_report_via_run_job_links_notification_log_to_job(
    session_factory,
):
    """End-to-end: run_job → send_recommendation_report → dispatcher →
    notification_logs.related_job_id == this run_job's job_run_id."""

    # Wrap the job so we can inject deterministic dry-run settings on the
    # work_session that run_job opens.
    def wrapped_send_recommendation(session):
        session.info["settings"] = _dry_run_settings()
        return send_recommendation_report(session)

    outcome = run_job(
        session_factory=session_factory,
        job_name=JOB_NAME_SEND_RECOMMENDATION_REPORT,
        fn=wrapped_send_recommendation,
    )

    # Engine had no universe → PARTIAL with dispatch DRY_RUN
    assert outcome.status == JOB_STATUS_PARTIAL
    assert outcome.result_summary["notification_status"] == "DRY_RUN"

    session = _read_session(session_factory)
    try:
        log = NotificationLogRepository(session).list()[0]
        assert log.status == "DRY_RUN"
        assert log.related_job_id == outcome.job_run_id
    finally:
        session.close()
