from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

import pytest
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool

import app.scheduler.jobs as scheduler_jobs
from app.analysis.technical_analyzer import TechnicalAnalyzer
from app.config.settings import Settings
from app.data.repositories import (
    DailyPriceRepository,
    HoldingCheckRepository,
    HoldingRepository,
    JobRunRepository,
    MarketCapRankingRepository,
    NotificationLogRepository,
    RecommendationRepository,
    RecommendationRunRepository,
    StockRepository,
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
    JOB_NAME_UPDATE_REPORT_CONSENSUS,
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
from tests.mocks.fake_kis_client import FakeKisDataProvider
from tests.mocks.kis_responses import DAILY_PRICE_RESPONSE, MARKET_CAP_RANKING_RESPONSE


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


def _market_cap_rows() -> list[dict]:
    return list(MARKET_CAP_RANKING_RESPONSE["output"])


def _daily_price_rows() -> list[dict]:
    return list(DAILY_PRICE_RESPONSE["output2"])


class FailingDailyPriceProvider(FakeKisDataProvider):
    def __init__(self, *, failing_symbols: set[str], **kwargs) -> None:
        super().__init__(**kwargs)
        self._failing_symbols = failing_symbols

    def fetch_daily_prices(self, symbol, start_date, end_date):
        if symbol in self._failing_symbols:
            self.calls.append(("fetch_daily_prices", (symbol, start_date, end_date)))
            raise RuntimeError(f"daily failed for {symbol}")
        return super().fetch_daily_prices(symbol, start_date, end_date)


def _market_close_config() -> dict:
    return {
        "target_date": date(2026, 5, 4),
        "start_date": date(2026, 5, 4),
        "end_date": date(2026, 5, 4),
        "market": "KOSPI",
        "limit": 2,
        "universe_name": "MARKET_CAP_TOP_500",
    }


def _seed_universe_members(session, *, name: str, symbols: list[str]) -> StockUniverse:
    universe = StockUniverseRepository(session).add(StockUniverse(name=name))
    session.flush()
    for symbol in symbols:
        StockUniverseMemberRepository(session).add(
            StockUniverseMember(universe_id=universe.universe_id, symbol=symbol),
        )
    session.flush()
    return universe


def _seed_flat_prices(
    session,
    *,
    symbol: str,
    n_bars: int,
    start_date: date = date(2026, 5, 1),
) -> None:
    for offset in range(n_bars):
        DailyPriceRepository(session).upsert(
            symbol=symbol,
            price_date=start_date + timedelta(days=offset),
            open_price=Decimal("100"),
            high_price=Decimal("100"),
            low_price=Decimal("100"),
            close_price=Decimal("100"),
            volume=1_000_000,
        )
    session.flush()


class FailingTechnicalAnalyzer:
    def __init__(self, *, failing_symbol: str) -> None:
        self._failing_symbol = failing_symbol
        self.seen_symbols: list[str] = []

    def analyze_latest(self, bars):
        symbol = bars[-1].symbol
        self.seen_symbols.append(symbol)
        if symbol == self._failing_symbol:
            raise RuntimeError(f"indicator failed for {symbol}")
        return TechnicalAnalyzer().analyze_latest(bars)


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

def test_collect_market_close_data_collects_rankings_and_daily_prices_success(
    session_factory,
):
    session = session_factory()
    try:
        provider = FakeKisDataProvider(
            market_cap_responses={
                ("KOSPI", date(2026, 5, 4)): _market_cap_rows(),
            },
            daily_price_responses={
                "005930": _daily_price_rows(),
                "000660": _daily_price_rows(),
            },
        )
        session.info["data_provider"] = provider
        session.info["market_close_config"] = _market_close_config()
        result = collect_market_close_data(session)
        session.commit()
    finally:
        session.close()

    assert result.status == JOB_STATUS_SUCCESS
    assert result.summary["phase"] == "8-wired"
    assert result.summary["market_cap_saved_rankings"] == 2
    assert result.summary["symbols_count"] == 2
    assert result.summary["daily_success_count"] == 2
    assert result.summary["daily_failure_count"] == 0
    assert result.summary["daily_saved_rows"] == 4
    assert result.error_message is None

    session2 = _read_session(session_factory)
    try:
        rankings = MarketCapRankingRepository(session2).list_by_date_market(
            date(2026, 5, 4),
            "KOSPI",
        )
        assert [r.symbol for r in rankings] == ["005930", "000660"]
        assert StockRepository(session2).get_by_symbol("005930") is not None
        assert DailyPriceRepository(session2).get_by_symbol_date(
            "005930",
            date(2026, 5, 4),
        ) is not None
    finally:
        session2.close()


def test_collect_market_close_data_uses_settings_when_no_job_config(
    session_factory,
    monkeypatch,
):
    fixed_today = date(2026, 5, 4)
    monkeypatch.setattr(
        "app.scheduler.jobs._today_in_default_timezone",
        lambda: fixed_today,
    )

    session = session_factory()
    try:
        provider = FakeKisDataProvider(
            market_cap_responses={("KOSDAQ", fixed_today): _market_cap_rows()},
            daily_price_responses={"005930": _daily_price_rows()},
        )
        session.info["data_provider"] = provider
        session.info["settings"] = Settings(
            collect_market="KOSDAQ",
            market_cap_limit=1,
            market_cap_universe_name="KOSDAQ_TOP_1",
            daily_price_lookback_days=3,
            daily_price_batch_size=1,
        )
        result = collect_market_close_data(session)
        session.commit()
    finally:
        session.close()

    assert result.status == JOB_STATUS_SUCCESS
    assert result.summary["market"] == "KOSDAQ"
    assert result.summary["market_cap_limit"] == 1
    assert result.summary["universe"] == "KOSDAQ_TOP_1"
    assert result.summary["lookback_days"] == 3
    assert result.summary["batch_size"] == 1
    assert result.summary["start_date"] == "2026-05-02"
    assert result.summary["end_date"] == "2026-05-04"
    assert provider.calls[0] == (
        "fetch_market_cap_rankings",
        ("KOSDAQ", fixed_today, 1),
    )
    assert provider.calls[1] == (
        "fetch_daily_prices",
        ("005930", date(2026, 5, 2), fixed_today),
    )


def test_collect_market_close_data_returns_partial_when_one_symbol_fails(
    session_factory,
):
    session = session_factory()
    try:
        provider = FailingDailyPriceProvider(
            failing_symbols={"000660"},
            market_cap_responses={
                ("KOSPI", date(2026, 5, 4)): _market_cap_rows(),
            },
            daily_price_responses={"005930": _daily_price_rows()},
        )
        session.info["data_provider"] = provider
        session.info["market_close_config"] = _market_close_config()
        result = collect_market_close_data(session)
        session.commit()
    finally:
        session.close()

    assert result.status == JOB_STATUS_PARTIAL
    assert result.error_message == "1 daily price collections failed"
    assert result.summary["daily_success_count"] == 1
    assert result.summary["daily_failure_count"] == 1
    assert result.summary["failures"] == [
        {
            "stage": "daily_prices",
            "symbol": "000660",
            "error_type": "RuntimeError",
            "message": "daily failed for 000660",
        },
    ]


def test_collect_market_close_data_returns_failed_when_all_symbols_fail(
    session_factory,
):
    session = session_factory()
    try:
        provider = FailingDailyPriceProvider(
            failing_symbols={"005930", "000660"},
            market_cap_responses={
                ("KOSPI", date(2026, 5, 4)): _market_cap_rows(),
            },
        )
        session.info["data_provider"] = provider
        session.info["market_close_config"] = _market_close_config()
        result = collect_market_close_data(session)
        session.commit()
    finally:
        session.close()

    assert result.status == JOB_STATUS_FAILED
    assert result.error_message == "all daily price collections failed"
    assert result.summary["daily_success_count"] == 0
    assert result.summary["daily_failure_count"] == 2
    assert {failure["symbol"] for failure in result.summary["failures"]} == {
        "005930",
        "000660",
    }


def test_collect_market_close_data_via_run_job_persists_partial_summary(
    session_factory,
):
    def wrapped(session):
        session.info["data_provider"] = FailingDailyPriceProvider(
            failing_symbols={"000660"},
            market_cap_responses={
                ("KOSPI", date(2026, 5, 4)): _market_cap_rows(),
            },
            daily_price_responses={"005930": _daily_price_rows()},
        )
        session.info["market_close_config"] = _market_close_config()
        return collect_market_close_data(session)

    outcome = run_job(
        session_factory=session_factory,
        job_name=JOB_NAME_COLLECT_MARKET_CLOSE,
        fn=wrapped,
    )

    assert outcome.status == JOB_STATUS_PARTIAL
    assert outcome.result_summary["daily_failure_count"] == 1

    session = _read_session(session_factory)
    try:
        row = JobRunRepository(session).list()[0]
        assert row.status == JOB_STATUS_PARTIAL
        assert row.result_summary["failures"][0]["symbol"] == "000660"
        assert row.error_message == "1 daily price collections failed"
    finally:
        session.close()


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
    assert result.summary["universe"] == "MARKET_CAP_TOP_500"


def test_calculate_technical_indicators_runs_indicator_service(session_factory):
    session = session_factory()
    try:
        _seed_universe_members(
            session,
            name="MARKET_CAP_TOP_500",
            symbols=["005930", "000660"],
        )
        _seed_flat_prices(session, symbol="005930", n_bars=5)
        _seed_flat_prices(session, symbol="000660", n_bars=5)
        session.commit()

        result = calculate_technical_indicators(session)
        session.commit()
    finally:
        session.close()

    assert result.status == JOB_STATUS_SUCCESS
    assert result.summary["members_count"] == 2
    assert result.summary["snapshots_saved"] == 2
    assert result.summary["success_count"] == 2
    assert result.summary["skipped_no_prices"] == 0
    assert result.summary["failure_count"] == 0

    session2 = _read_session(session_factory)
    try:
        indicator = StockIndicatorRepository(session2).get_latest_by_symbol("005930")
        assert indicator is not None
        assert StockIndicatorRepository(session2).get_latest_by_symbol("000660") is not None
    finally:
        session2.close()


def test_calculate_technical_indicators_partial_when_symbol_has_no_prices(
    session_factory,
):
    session = session_factory()
    try:
        _seed_universe_members(
            session,
            name="MARKET_CAP_TOP_500",
            symbols=["005930", "000660"],
        )
        _seed_flat_prices(session, symbol="005930", n_bars=5)
        session.commit()

        result = calculate_technical_indicators(session)
        session.commit()
    finally:
        session.close()

    assert result.status == JOB_STATUS_PARTIAL
    assert result.error_message is None
    assert result.summary["success_count"] == 1
    assert result.summary["skipped_no_prices"] == 1
    assert result.summary["failure_count"] == 0
    assert result.summary["skipped"] == [
        {"symbol": "000660", "reason": "NO_DAILY_PRICES"},
    ]


def test_calculate_technical_indicators_partial_when_one_symbol_fails(
    session_factory,
):
    session = session_factory()
    try:
        _seed_universe_members(
            session,
            name="MARKET_CAP_TOP_500",
            symbols=["005930", "000660"],
        )
        _seed_flat_prices(session, symbol="005930", n_bars=5)
        _seed_flat_prices(session, symbol="000660", n_bars=5)
        session.info["technical_analyzer"] = FailingTechnicalAnalyzer(
            failing_symbol="000660",
        )
        session.commit()

        result = calculate_technical_indicators(session)
        session.commit()
    finally:
        session.close()

    assert result.status == JOB_STATUS_PARTIAL
    assert result.error_message == "1 technical indicator calculations failed"
    assert result.summary["success_count"] == 1
    assert result.summary["failure_count"] == 1
    assert result.summary["failures"] == [
        {
            "symbol": "000660",
            "error_type": "RuntimeError",
            "message": "indicator failed for 000660",
        },
    ]


def test_calculate_technical_indicators_uses_settings_override(session_factory):
    session = session_factory()
    try:
        _seed_universe_members(
            session,
            name="CUSTOM_TOP",
            symbols=["005930"],
        )
        _seed_flat_prices(session, symbol="005930", n_bars=40)
        session.info["settings"] = Settings(
            indicator_universe_name="CUSTOM_TOP",
            indicator_lookback_days=30,
            indicator_batch_size=1,
        )
        session.commit()

        result = calculate_technical_indicators(session)
        session.commit()
    finally:
        session.close()

    assert result.status == JOB_STATUS_SUCCESS
    assert result.summary["universe"] == "CUSTOM_TOP"
    assert result.summary["lookback_days"] == 30
    assert result.summary["batch_size"] == 1

    session2 = _read_session(session_factory)
    try:
        indicator = StockIndicatorRepository(session2).get_latest_by_symbol("005930")
        assert indicator is not None
        assert indicator.ma20 is not None
        assert indicator.ma60 is None
    finally:
        session2.close()


# ---------- send_recommendation_report ----------

def test_send_recommendation_report_success_no_data_when_no_run(session_factory):
    session = _open_session(session_factory)
    try:
        result = send_recommendation_report(session)
        session.commit()
    finally:
        session.close()

    assert result.status == JOB_STATUS_SUCCESS
    assert result.summary["run_id"] is None
    assert result.summary["run_date"] is None
    assert result.summary["telegram_sent"] is False
    assert result.summary["dry_run"] is False
    assert result.summary["notification_status"] == "NO_DATA"
    assert result.summary["recommendation_count"] == 0
    assert result.summary["telegram_sent_flag_updated"] is False
    assert result.summary["notification_log_id"] is None
    assert result.summary["message_length"] == 0

    session2 = _read_session(session_factory)
    try:
        assert NotificationLogRepository(session2).list() == []
    finally:
        session2.close()


def test_send_recommendation_report_success_dry_run_with_latest_run(session_factory):
    session = _open_session(session_factory)
    try:
        latest_run = RecommendationRunRepository(session).add(
            RecommendationRun(
                run_date=date(2026, 5, 4),
                started_at=datetime(2026, 5, 4, 6, 0, tzinfo=timezone.utc),
                status="SUCCESS",
                telegram_sent=False,
            ),
        )
        session.flush()
        RecommendationRepository(session).add(
            Recommendation(
                run_id=latest_run.run_id, rank=1, market="KOSPI",
                symbol="005930", name="Samsung Electronics",
                grade="A", total_score=Decimal("80"),
            ),
        )
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
        latest_run_id = latest_run.run_id

        result = send_recommendation_report(session)
        session.commit()
    finally:
        session.close()

    assert result.status == JOB_STATUS_SUCCESS
    assert result.summary["run_id"] == latest_run_id
    assert result.summary["run_date"] == "2026-05-04"
    assert result.summary["telegram_sent"] is False
    assert result.summary["dry_run"] is True
    assert result.summary["recommendation_count"] == 1
    assert result.summary["notification_status"] == "DRY_RUN"
    assert result.summary["notification_log_id"] is not None
    assert result.summary["telegram_sent_flag_updated"] is False
    assert result.summary["message_length"] > 0

    session2 = _read_session(session_factory)
    try:
        run = RecommendationRunRepository(session2).get(result.summary["run_id"])
        assert run is not None
        assert run.telegram_sent is False  # DRY_RUN does not set the flag
        assert RecommendationRepository(session2).list_by_run_id(run.run_id)
        log = NotificationLogRepository(session2).list()[0]
        assert log.status == "DRY_RUN"
        assert log.message_type == "REPORT"
    finally:
        session2.close()


def test_send_recommendation_report_via_run_job_failed_when_dispatcher_fails(
    session_factory,
    monkeypatch,
):
    session = _open_session(session_factory)
    try:
        run = RecommendationRunRepository(session).add(
            RecommendationRun(
                run_date=date(2026, 5, 4),
                started_at=datetime(2026, 5, 4, 6, 0, tzinfo=timezone.utc),
                status="SUCCESS",
                telegram_sent=False,
            ),
        )
        session.flush()
        RecommendationRepository(session).add(
            Recommendation(
                run_id=run.run_id, rank=1, market="KOSPI",
                symbol="005930", name="Samsung Electronics",
                grade="A", total_score=Decimal("80"),
            ),
        )
        session.commit()
    finally:
        session.close()

    class FailingDispatcher:
        def dispatch(self, *, run_id, related_job_id=None):
            raise RuntimeError("dispatcher failed")

    monkeypatch.setattr(
        scheduler_jobs,
        "_build_recommendation_dispatcher",
        lambda session, *, notifier: FailingDispatcher(),
    )

    def wrapped_send_recommendation(session):
        session.info["settings"] = _dry_run_settings()
        return send_recommendation_report(session)

    outcome = run_job(
        session_factory=session_factory,
        job_name=JOB_NAME_SEND_RECOMMENDATION_REPORT,
        fn=wrapped_send_recommendation,
    )

    assert outcome.status == JOB_STATUS_FAILED
    assert outcome.result_summary is None
    assert "dispatcher failed" in outcome.error_message

    session2 = _read_session(session_factory)
    try:
        run = RecommendationRunRepository(session2).latest()
        assert run is not None
        assert run.telegram_sent is False
        assert NotificationLogRepository(session2).list() == []
    finally:
        session2.close()


# ---------- pre/post-market holding check ----------

def _seed_active_holding(
    session,
    *,
    symbol: str = "005930",
    quantity: Decimal = Decimal("10"),
    avg_buy_price: Decimal = Decimal("100"),
    close_price: Decimal = Decimal("110"),
    ma20: Decimal | None = Decimal("100"),
    technical_score: Decimal = Decimal("80"),
    price_date: date = date(2026, 5, 4),
) -> None:
    HoldingRepository(session).add(
        Holding(
            symbol=symbol,
            quantity=quantity,
            avg_buy_price=avg_buy_price,
            is_active=True,
        ),
    )
    DailyPriceRepository(session).upsert(
        symbol=symbol,
        price_date=price_date,
        open_price=close_price,
        high_price=close_price,
        low_price=close_price,
        close_price=close_price,
        volume=1_000_000,
    )
    StockIndicatorRepository(session).upsert(
        symbol=symbol,
        indicator_date=price_date,
        technical_score=technical_score,
        ma20=ma20,
    )


def test_pre_market_holding_check_with_no_holdings_returns_no_data(session_factory):
    session = _open_session(session_factory)
    try:
        result = run_pre_market_holding_check(session)
        session.commit()
    finally:
        session.close()

    assert result.status == JOB_STATUS_SUCCESS
    assert result.summary["check_type"] == "PRE_MARKET"
    assert isinstance(result.summary["check_date"], str)
    assert result.summary["checked_count"] == 0
    assert result.summary["saved_count"] == 0
    assert result.summary["alert_count"] == 0
    assert result.summary["alert_sent_count"] == 0
    assert result.summary["holding_check_count"] == 0
    assert result.summary["telegram_sent"] is False
    assert result.summary["dry_run"] is False
    assert result.summary["notification_status"] == "NO_DATA"
    assert result.summary["notification_log_id"] is None
    assert result.summary["message_length"] == 0

    session2 = _read_session(session_factory)
    try:
        assert NotificationLogRepository(session2).list() == []
        assert HoldingCheckRepository(session2).list_by_symbol("005930") == []
    finally:
        session2.close()


def test_pre_market_holding_check_processes_active_holdings(session_factory):
    session = _open_session(session_factory)
    try:
        _seed_active_holding(session)
        session.commit()

        result = run_pre_market_holding_check(session)
        session.commit()
    finally:
        session.close()

    assert result.status == JOB_STATUS_SUCCESS
    assert result.summary["check_type"] == "PRE_MARKET"
    assert result.summary["checked_count"] == 1
    assert result.summary["saved_count"] == 1
    assert result.summary["alert_count"] == 0
    assert result.summary["alert_sent_count"] == 0
    assert result.summary["holding_check_count"] == 1
    assert result.summary["dry_run"] is True
    assert result.summary["notification_status"] == "DRY_RUN"
    assert result.summary["telegram_sent"] is False
    assert result.summary["notification_log_id"] is not None
    assert result.summary["message_length"] > 0

    session2 = _read_session(session_factory)
    try:
        checks = HoldingCheckRepository(session2).list_by_symbol("005930")
        assert len(checks) == 1
        assert checks[0].check_type == "PRE_MARKET"
        log = NotificationLogRepository(session2).list()[0]
        assert log.status == "DRY_RUN"
        assert log.message_type == "REPORT"
    finally:
        session2.close()


def test_post_market_holding_check_processes_active_holdings(session_factory):
    session = _open_session(session_factory)
    try:
        _seed_active_holding(session)
        session.commit()

        result = run_post_market_holding_check(session)
        session.commit()
    finally:
        session.close()

    assert result.status == JOB_STATUS_SUCCESS
    assert result.summary["check_type"] == "POST_MARKET"
    assert result.summary["checked_count"] == 1
    assert result.summary["saved_count"] == 1
    assert result.summary["holding_check_count"] == 1
    assert result.summary["dry_run"] is True
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


def test_pre_market_holding_check_dispatches_alert_for_high_risk_holding(
    session_factory,
):
    """avg=100, current=80, ma20=100 → MA20_BREAKDOWN + STOP_LOSS_NEAR
    → risk_level=HIGH, alert=True. The alert dispatcher records both a REPORT
    notification_logs row and a HIGH_RISK ALERT row."""
    session = _open_session(session_factory)
    try:
        _seed_active_holding(
            session,
            avg_buy_price=Decimal("100"),
            close_price=Decimal("80"),
            ma20=Decimal("100"),
            technical_score=Decimal("80"),
        )
        session.commit()

        result = run_pre_market_holding_check(session)
        session.commit()
    finally:
        session.close()

    assert result.status == JOB_STATUS_SUCCESS
    assert result.summary["check_type"] == "PRE_MARKET"
    assert result.summary["saved_count"] == 1
    assert result.summary["alert_count"] == 1
    assert result.summary["alert_sent_count"] == 1
    assert result.summary["dry_run"] is True
    assert result.summary["notification_status"] == "DRY_RUN"

    session2 = _read_session(session_factory)
    try:
        checks = HoldingCheckRepository(session2).list_by_symbol("005930")
        assert len(checks) == 1
        assert checks[0].alert is True

        logs = NotificationLogRepository(session2).list()
        report_logs = [log for log in logs if log.message_type == "REPORT"]
        alert_logs = [log for log in logs if log.message_type == "ALERT"]
        assert len(report_logs) == 1
        assert len(alert_logs) == 1
        assert alert_logs[0].status == "DRY_RUN"
        assert alert_logs[0].target == (
            f"ALERT_HOLDING:005930:{result.summary['check_date']}:"
            "PRE_MARKET:HIGH_RISK"
        )
    finally:
        session2.close()


def test_holding_check_via_run_job_failed_when_dispatcher_fails(
    session_factory,
    monkeypatch,
):
    """Dispatcher exception inside the holding-check job propagates to run_job,
    which records FAILED and rolls back the work session — no holding_checks
    persisted, no notification_logs."""
    seed = _open_session(session_factory)
    try:
        _seed_active_holding(seed)
        seed.commit()
    finally:
        seed.close()

    class FailingDispatcher:
        def dispatch(self, *, check_date, check_type, related_job_id=None):
            raise RuntimeError("holding dispatcher failed")

    monkeypatch.setattr(
        scheduler_jobs,
        "_build_holding_check_dispatcher",
        lambda session, *, notifier: FailingDispatcher(),
    )

    def wrapped(session):
        session.info["settings"] = _dry_run_settings()
        return run_pre_market_holding_check(session)

    outcome = run_job(
        session_factory=session_factory,
        job_name=JOB_NAME_PRE_MARKET_HOLDING_CHECK,
        fn=wrapped,
    )

    assert outcome.status == JOB_STATUS_FAILED
    assert outcome.result_summary is None
    assert "holding dispatcher failed" in outcome.error_message

    session2 = _read_session(session_factory)
    try:
        # work session rolled back → no holding_checks, no notification_logs
        assert HoldingCheckRepository(session2).list_by_symbol("005930") == []
        assert NotificationLogRepository(session2).list() == []
        # job_runs row still recorded
        runs = JobRunRepository(session2).list()
        assert len(runs) == 1
        assert runs[0].job_name == JOB_NAME_PRE_MARKET_HOLDING_CHECK
        assert runs[0].status == JOB_STATUS_FAILED
    finally:
        session2.close()


def test_holding_check_via_run_job_links_notification_log_to_job(session_factory):
    """End-to-end: run_job → run_pre_market_holding_check → dispatcher →
    notification_logs.related_job_id == this run_job's job_run_id."""
    seed = _open_session(session_factory)
    try:
        _seed_active_holding(seed)
        seed.commit()
    finally:
        seed.close()

    def wrapped(session):
        session.info["settings"] = _dry_run_settings()
        return run_pre_market_holding_check(session)

    outcome = run_job(
        session_factory=session_factory,
        job_name=JOB_NAME_PRE_MARKET_HOLDING_CHECK,
        fn=wrapped,
    )

    assert outcome.status == JOB_STATUS_SUCCESS
    assert outcome.result_summary["notification_status"] == "DRY_RUN"
    assert outcome.result_summary["dry_run"] is True
    assert outcome.result_summary["check_type"] == "PRE_MARKET"

    session2 = _read_session(session_factory)
    try:
        log = [
            log for log in NotificationLogRepository(session2).list()
            if log.message_type == "REPORT"
        ][0]
        assert log.related_job_id == outcome.job_run_id
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
    assert result.summary["data_status"] == "NO_DATA"
    assert result.summary["processed_runs"] == 0
    assert result.summary["processed_count"] == 0
    assert result.summary["processed_recommendations"] == 0
    assert result.summary["upserted_results"] == 0
    assert result.summary["pending_count"] == 0
    assert result.summary["success_count"] == 0
    assert result.summary["failed_count"] == 0
    assert result.summary["skipped_no_reference"] == 0
    assert result.summary["lookback_days"] >= 1
    assert result.error_message is None


def _seed_run_with_recommendation(
    session,
    *,
    symbol: str,
    name: str = "테스트종목",
    run_date: date = date(2026, 5, 4),
    rank: int = 1,
    run: RecommendationRun | None = None,
) -> tuple[RecommendationRun, int]:
    if run is None:
        run = RecommendationRunRepository(session).add(
            RecommendationRun(
                run_date=run_date,
                started_at=datetime(run_date.year, run_date.month, run_date.day, tzinfo=timezone.utc),
                status="SUCCESS",
                telegram_sent=False,
            ),
        )
        session.flush()
    rec = RecommendationRepository(session).add(
        Recommendation(
            run_id=run.run_id, rank=rank, market="KOSPI",
            symbol=symbol, name=name,
            grade="A", total_score=Decimal("80"),
        ),
    )
    return run, rec.id


def test_update_recommendation_results_processes_seeded_run(session_factory):
    session = session_factory()
    rec_id: int
    try:
        _, rec_id = _seed_run_with_recommendation(session, symbol="005930", name="삼성전자")
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

        result = update_recommendation_results(session)
        session.commit()
    finally:
        session.close()

    assert result.status == JOB_STATUS_SUCCESS
    assert result.summary["data_status"] == "SUCCESS"
    assert result.summary["processed_runs"] == 1
    assert result.summary["processed_count"] == 1
    assert result.summary["processed_recommendations"] == 1
    assert result.summary["skipped_no_reference"] == 0
    assert result.summary["upserted_results"] == 4
    assert result.summary["success_count"] >= 1
    assert result.error_message is None

    session2 = _read_session(session_factory)
    try:
        from app.data.repositories import RecommendationResultRepository

        rows = RecommendationResultRepository(session2).list_by_recommendation_id(rec_id)
        assert {r.days_after for r in rows} == {1, 3, 5, 20}
    finally:
        session2.close()


def test_update_recommendation_results_partial_when_no_reference_price(
    session_factory,
):
    """Recommendation exists but no daily_prices on/before run_date → all 4
    days_after rows upserted as PENDING with skipped_no_reference=1, job
    returns PARTIAL with data_status=PARTIAL."""
    session = session_factory()
    rec_id: int
    try:
        _, rec_id = _seed_run_with_recommendation(session, symbol="000660", name="SK하이닉스")
        session.commit()

        result = update_recommendation_results(session)
        session.commit()
    finally:
        session.close()

    assert result.status == JOB_STATUS_PARTIAL
    assert result.summary["data_status"] == "PARTIAL"
    assert result.summary["processed_count"] == 1
    assert result.summary["skipped_no_reference"] == 1
    assert result.summary["upserted_results"] == 4
    assert result.summary["pending_count"] == 4
    assert result.summary["success_count"] == 0
    assert result.summary["failed_count"] == 0
    assert "1 recommendations had no reference price" in result.error_message

    session2 = _read_session(session_factory)
    try:
        from app.data.repositories import RecommendationResultRepository

        rows = RecommendationResultRepository(session2).list_by_recommendation_id(rec_id)
        assert {r.days_after for r in rows} == {1, 3, 5, 20}
        assert all(r.result_status == "PENDING" for r in rows)
        assert all(r.close_return is None for r in rows)
    finally:
        session2.close()


def test_update_recommendation_results_partial_when_one_symbol_missing_prices(
    session_factory,
):
    """Two recommendations in the same run: one with prices (SUCCESS path),
    one without (PENDING + skipped_no_reference). Job returns PARTIAL."""
    session = session_factory()
    try:
        run, _ = _seed_run_with_recommendation(session, symbol="005930", name="삼성전자", rank=1)
        _seed_run_with_recommendation(
            session, symbol="000660", name="SK하이닉스", rank=2, run=run,
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

        result = update_recommendation_results(session)
        session.commit()
    finally:
        session.close()

    assert result.status == JOB_STATUS_PARTIAL
    assert result.summary["data_status"] == "PARTIAL"
    assert result.summary["processed_count"] == 2
    assert result.summary["skipped_no_reference"] == 1
    assert result.summary["upserted_results"] == 8  # 4 days_after × 2 recs
    assert result.summary["success_count"] >= 1
    assert "1 recommendations had no reference price" in result.error_message


def test_update_recommendation_results_via_run_job_records_partial_summary(
    session_factory,
):
    def wrapped(session):
        _, _ = _seed_run_with_recommendation(session, symbol="000660", name="SK하이닉스")
        return update_recommendation_results(session)

    outcome = run_job(
        session_factory=session_factory,
        job_name=JOB_NAME_UPDATE_RECOMMENDATION_RESULTS,
        fn=wrapped,
    )

    assert outcome.status == JOB_STATUS_PARTIAL
    assert outcome.result_summary["data_status"] == "PARTIAL"
    assert outcome.result_summary["skipped_no_reference"] == 1
    assert "1 recommendations had no reference price" in outcome.error_message

    session = _read_session(session_factory)
    try:
        row = JobRunRepository(session).list()[0]
        assert row.status == JOB_STATUS_PARTIAL
        assert row.result_summary["data_status"] == "PARTIAL"
    finally:
        session.close()


# ---------- registry sanity ----------

def test_job_functions_registry_covers_all_seven_jobs():
    """v0.4 Phase B 에서 update_report_consensus_snapshots 가 추가되어 7개."""
    assert set(JOB_FUNCTIONS) == {
        JOB_NAME_COLLECT_MARKET_CLOSE,
        JOB_NAME_CALCULATE_INDICATORS,
        JOB_NAME_SEND_RECOMMENDATION_REPORT,
        JOB_NAME_PRE_MARKET_HOLDING_CHECK,
        JOB_NAME_POST_MARKET_HOLDING_CHECK,
        JOB_NAME_UPDATE_RECOMMENDATION_RESULTS,
        JOB_NAME_UPDATE_REPORT_CONSENSUS,
    }


def test_run_job_with_registered_function(session_factory):
    """Smoke test: wrapper + registry can drive a registered job end-to-end."""
    def wrapped(session):
        session.info["data_provider"] = FakeKisDataProvider(
            market_cap_responses={
                ("KOSPI", date(2026, 5, 4)): _market_cap_rows(),
            },
            daily_price_responses={
                "005930": _daily_price_rows(),
                "000660": _daily_price_rows(),
            },
        )
        session.info["market_close_config"] = _market_close_config()
        return JOB_FUNCTIONS[JOB_NAME_COLLECT_MARKET_CLOSE](session)

    outcome = run_job(
        session_factory=session_factory,
        job_name=JOB_NAME_COLLECT_MARKET_CLOSE,
        fn=wrapped,
    )
    assert outcome.status == JOB_STATUS_SUCCESS
    assert outcome.result_summary["phase"] == "8-wired"
    assert outcome.result_summary["daily_success_count"] == 2


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

    seed_session = _open_session(session_factory)
    try:
        run = RecommendationRunRepository(seed_session).add(
            RecommendationRun(
                run_date=date(2026, 5, 4),
                started_at=datetime(2026, 5, 4, 6, 0, tzinfo=timezone.utc),
                status="SUCCESS",
                telegram_sent=False,
            ),
        )
        seed_session.flush()
        RecommendationRepository(seed_session).add(
            Recommendation(
                run_id=run.run_id, rank=1, market="KOSPI",
                symbol="005930", name="Samsung Electronics",
                grade="A", total_score=Decimal("80"),
            ),
        )
        seed_session.commit()
    finally:
        seed_session.close()

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
    assert outcome.status == JOB_STATUS_SUCCESS
    assert outcome.result_summary["notification_status"] == "DRY_RUN"
    assert outcome.result_summary["dry_run"] is True

    session = _read_session(session_factory)
    try:
        log = NotificationLogRepository(session).list()[0]
        assert log.status == "DRY_RUN"
        assert log.related_job_id == outcome.job_run_id
    finally:
        session.close()
