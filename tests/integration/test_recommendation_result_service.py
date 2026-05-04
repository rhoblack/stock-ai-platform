from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

import pytest

from app.data.repositories import (
    DailyPriceRepository,
    RecommendationRepository,
    RecommendationResultRepository,
    RecommendationRunRepository,
)
from app.db import Base
from app.db.models import (
    Recommendation,
    RecommendationRun,
)
from app.db.session import create_db_engine, create_session_factory
from app.decision.recommendation_result_service import (
    RESULT_STATUS_FAILED,
    RESULT_STATUS_PENDING,
    RESULT_STATUS_SUCCESS,
    RecommendationResultRunResult,
    RecommendationResultService,
)


@pytest.fixture()
def session():
    engine = create_db_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    factory = create_session_factory(engine)
    s = factory()
    try:
        yield s
    finally:
        s.close()
        Base.metadata.drop_all(engine)


def _service(session) -> RecommendationResultService:
    return RecommendationResultService(
        recommendation_run_repository=RecommendationRunRepository(session),
        recommendation_repository=RecommendationRepository(session),
        recommendation_result_repository=RecommendationResultRepository(session),
        daily_price_repository=DailyPriceRepository(session),
    )


def _seed_run_and_recommendation(
    session,
    *,
    run_date: date = date(2026, 5, 4),
    symbol: str = "005930",
    name: str = "삼성전자",
) -> Recommendation:
    run = RecommendationRunRepository(session).add(
        RecommendationRun(
            run_date=run_date,
            started_at=datetime.combine(run_date, datetime.min.time(), tzinfo=timezone.utc),
            status="SUCCESS",
            telegram_sent=False,
        ),
    )
    session.flush()
    rec = RecommendationRepository(session).add(
        Recommendation(
            run_id=run.run_id,
            rank=1,
            market="KOSPI",
            symbol=symbol,
            name=name,
            grade="A",
            total_score=Decimal("80"),
        ),
    )
    session.flush()
    session.commit()
    return rec


def _seed_daily(session, *, symbol: str, price_date: date,
                open_p: Decimal, high: Decimal, low: Decimal, close: Decimal,
                volume: int = 1_000_000) -> None:
    DailyPriceRepository(session).upsert(
        symbol=symbol,
        price_date=price_date,
        open_price=open_p,
        high_price=high,
        low_price=low,
        close_price=close,
        volume=volume,
    )
    session.flush()


def _seed_flat_window(
    session,
    *,
    symbol: str,
    reference_date: date,
    reference_close: Decimal,
    days: int,
    daily_close: Decimal | None = None,
    daily_high: Decimal | None = None,
    daily_low: Decimal | None = None,
) -> None:
    """Reference bar at ``reference_date`` + ``days`` bars after."""
    _seed_daily(
        session, symbol=symbol, price_date=reference_date,
        open_p=reference_close, high=reference_close,
        low=reference_close, close=reference_close,
    )
    close = daily_close if daily_close is not None else reference_close
    high = daily_high if daily_high is not None else close
    low = daily_low if daily_low is not None else close
    for offset in range(1, days + 1):
        _seed_daily(
            session, symbol=symbol,
            price_date=reference_date + timedelta(days=offset),
            open_p=close, high=high, low=low, close=close,
        )
    session.commit()


# ---------- success / failed / pending classification ----------

def test_close_return_meets_success_threshold(session):
    rec = _seed_run_and_recommendation(session)
    # Day 0: close=100. Day 1: close=101.5 (+1.5% close, no -5% drop)
    # → SUCCESS via close_return ≥ 1
    _seed_daily(session, symbol="005930", price_date=date(2026, 5, 4),
                open_p=Decimal("100"), high=Decimal("100"),
                low=Decimal("100"), close=Decimal("100"))
    _seed_daily(session, symbol="005930", price_date=date(2026, 5, 5),
                open_p=Decimal("100"), high=Decimal("102"),
                low=Decimal("99"), close=Decimal("101.5"))
    session.commit()

    result = _service(session).update_results(as_of=date(2026, 5, 25))
    session.commit()

    assert isinstance(result, RecommendationResultRunResult)
    assert result.processed_recommendations == 1

    rows = RecommendationResultRepository(session).list_by_recommendation_id(rec.id)
    by_n = {r.days_after: r for r in rows}
    one_day = by_n[1]
    assert one_day.result_status == RESULT_STATUS_SUCCESS
    assert one_day.close_return == Decimal("1.5000")
    assert one_day.high_return == Decimal("2.0000")
    assert one_day.low_return == Decimal("-1.0000")
    assert one_day.open_return == Decimal("0.0000")
    assert one_day.result_date == date(2026, 5, 5)


def test_high_return_threshold_marks_success(session):
    rec = _seed_run_and_recommendation(session)
    # Reference 100, day 1 high 105 (+5%) -> SUCCESS via high_return
    _seed_daily(session, symbol="005930", price_date=date(2026, 5, 4),
                open_p=Decimal("100"), high=Decimal("100"),
                low=Decimal("100"), close=Decimal("100"))
    _seed_daily(session, symbol="005930", price_date=date(2026, 5, 5),
                open_p=Decimal("100"), high=Decimal("105"),
                low=Decimal("99"), close=Decimal("100"))
    session.commit()

    _service(session).update_results(as_of=date(2026, 5, 25))
    session.commit()

    one_day = RecommendationResultRepository(session).get_by_recommendation_days(
        recommendation_id=rec.id, days_after=1,
    )
    assert one_day.result_status == RESULT_STATUS_SUCCESS
    assert one_day.high_return == Decimal("5.0000")
    assert one_day.max_return == Decimal("5.0000")


def test_low_return_threshold_marks_failed_even_with_upside(session):
    rec = _seed_run_and_recommendation(session)
    # +6% high but -7% low -> FAILED priority
    _seed_daily(session, symbol="005930", price_date=date(2026, 5, 4),
                open_p=Decimal("100"), high=Decimal("100"),
                low=Decimal("100"), close=Decimal("100"))
    _seed_daily(session, symbol="005930", price_date=date(2026, 5, 5),
                open_p=Decimal("100"), high=Decimal("106"),
                low=Decimal("93"), close=Decimal("100"))
    session.commit()

    _service(session).update_results(as_of=date(2026, 5, 25))
    session.commit()

    one_day = RecommendationResultRepository(session).get_by_recommendation_days(
        recommendation_id=rec.id, days_after=1,
    )
    assert one_day.result_status == RESULT_STATUS_FAILED
    assert one_day.low_return == Decimal("-7.0000")
    assert one_day.high_return == Decimal("6.0000")


def test_mild_move_remains_pending(session):
    rec = _seed_run_and_recommendation(session)
    # +0.5% close, +1% high, -0.5% low -> neither SUCCESS nor FAILED
    _seed_daily(session, symbol="005930", price_date=date(2026, 5, 4),
                open_p=Decimal("100"), high=Decimal("100"),
                low=Decimal("100"), close=Decimal("100"))
    _seed_daily(session, symbol="005930", price_date=date(2026, 5, 5),
                open_p=Decimal("100"), high=Decimal("101"),
                low=Decimal("99.5"), close=Decimal("100.5"))
    session.commit()

    _service(session).update_results(as_of=date(2026, 5, 25))
    session.commit()

    one_day = RecommendationResultRepository(session).get_by_recommendation_days(
        recommendation_id=rec.id, days_after=1,
    )
    assert one_day.result_status == RESULT_STATUS_PENDING
    assert one_day.close_return == Decimal("0.5000")


# ---------- 1/3/5/20 days_after ----------

def test_all_four_days_after_evaluated(session):
    rec = _seed_run_and_recommendation(session)
    # Reference 100; price stays flat for all bars
    _seed_flat_window(
        session, symbol="005930",
        reference_date=date(2026, 5, 4),
        reference_close=Decimal("100"),
        days=25,
    )

    _service(session).update_results(as_of=date(2026, 6, 30))
    session.commit()

    rows = RecommendationResultRepository(session).list_by_recommendation_id(rec.id)
    by_n = {r.days_after: r for r in rows}
    assert set(by_n) == {1, 3, 5, 20}
    for days in (1, 3, 5, 20):
        assert by_n[days].close_return == Decimal("0.0000")
        # Flat -> PENDING (no signal)
        assert by_n[days].result_status == RESULT_STATUS_PENDING


# ---------- pending / no data ----------

def test_pending_when_verification_window_empty(session):
    rec = _seed_run_and_recommendation(session)
    # Only the reference bar exists; no prices after
    _seed_daily(session, symbol="005930", price_date=date(2026, 5, 4),
                open_p=Decimal("100"), high=Decimal("100"),
                low=Decimal("100"), close=Decimal("100"))
    session.commit()

    result = _service(session).update_results(as_of=date(2026, 5, 4))
    session.commit()

    rows = RecommendationResultRepository(session).list_by_recommendation_id(rec.id)
    by_n = {r.days_after: r for r in rows}
    for days in (1, 3, 5, 20):
        assert by_n[days].result_status == RESULT_STATUS_PENDING
        assert by_n[days].close_return is None
        assert by_n[days].open_return is None
        assert by_n[days].high_return is None
        assert by_n[days].low_return is None
        assert by_n[days].max_return is None
        assert by_n[days].max_drawdown is None

    assert result.pending_count == 4
    assert result.success_count == 0
    assert result.failed_count == 0


def test_pending_when_no_reference_price_at_all(session):
    rec = _seed_run_and_recommendation(session)
    # No daily_prices anywhere → no reference

    result = _service(session).update_results(as_of=date(2026, 5, 25))
    session.commit()

    assert result.skipped_no_reference == 1
    rows = RecommendationResultRepository(session).list_by_recommendation_id(rec.id)
    assert {r.days_after for r in rows} == {1, 3, 5, 20}
    assert all(r.result_status == RESULT_STATUS_PENDING for r in rows)
    assert all(r.close_return is None for r in rows)


def test_reference_falls_back_to_latest_on_or_before_run_date(session):
    """Run on a non-trading day uses prior trading day's close as reference."""
    # run_date = 2026-05-09 (Saturday). Latest daily on 2026-05-08 (Friday).
    rec = _seed_run_and_recommendation(session, run_date=date(2026, 5, 9))
    _seed_daily(session, symbol="005930", price_date=date(2026, 5, 8),
                open_p=Decimal("100"), high=Decimal("100"),
                low=Decimal("100"), close=Decimal("100"))
    _seed_daily(session, symbol="005930", price_date=date(2026, 5, 11),
                open_p=Decimal("100"), high=Decimal("105"),
                low=Decimal("99"), close=Decimal("103"))
    session.commit()

    _service(session).update_results(as_of=date(2026, 5, 25))
    session.commit()

    # days_after=3 against reference_date=2026-05-08 → target 2026-05-11
    three_day = RecommendationResultRepository(session).get_by_recommendation_days(
        recommendation_id=rec.id, days_after=3,
    )
    assert three_day.close_return == Decimal("3.0000")
    assert three_day.result_status == RESULT_STATUS_SUCCESS
    assert three_day.result_date == date(2026, 5, 11)


# ---------- max_drawdown ----------

def test_max_drawdown_uses_peak_to_trough(session):
    rec = _seed_run_and_recommendation(session)
    # Reference 100. Day 1 high 110, day 2 low 88 → peak=110, trough=88,
    # drawdown = (88 - 110) / 110 * 100 = -20.0
    _seed_daily(session, symbol="005930", price_date=date(2026, 5, 4),
                open_p=Decimal("100"), high=Decimal("100"),
                low=Decimal("100"), close=Decimal("100"))
    _seed_daily(session, symbol="005930", price_date=date(2026, 5, 5),
                open_p=Decimal("100"), high=Decimal("110"),
                low=Decimal("100"), close=Decimal("110"))
    _seed_daily(session, symbol="005930", price_date=date(2026, 5, 6),
                open_p=Decimal("110"), high=Decimal("110"),
                low=Decimal("88"), close=Decimal("90"))
    _seed_daily(session, symbol="005930", price_date=date(2026, 5, 7),
                open_p=Decimal("90"), high=Decimal("95"),
                low=Decimal("90"), close=Decimal("92"))
    session.commit()

    _service(session).update_results(as_of=date(2026, 5, 25))
    session.commit()

    three_day = RecommendationResultRepository(session).get_by_recommendation_days(
        recommendation_id=rec.id, days_after=3,
    )
    assert three_day.max_drawdown == Decimal("-20.0000")
    assert three_day.high_return == Decimal("10.0000")
    assert three_day.low_return == Decimal("-12.0000")
    # Low_return ≤ -5 → FAILED
    assert three_day.result_status == RESULT_STATUS_FAILED


# ---------- upsert idempotency ----------

def test_repeated_calls_do_not_duplicate_rows(session):
    rec = _seed_run_and_recommendation(session)
    _seed_flat_window(
        session, symbol="005930",
        reference_date=date(2026, 5, 4),
        reference_close=Decimal("100"),
        days=25,
    )

    service = _service(session)
    service.update_results(as_of=date(2026, 6, 30))
    session.commit()
    service.update_results(as_of=date(2026, 6, 30))
    session.commit()

    rows = RecommendationResultRepository(session).list_by_recommendation_id(rec.id)
    assert len(rows) == 4  # one per days_after, not 8


def test_upsert_overwrites_pending_with_resolved_status(session):
    rec = _seed_run_and_recommendation(session)
    # Run 1: only reference bar → all PENDING
    _seed_daily(session, symbol="005930", price_date=date(2026, 5, 4),
                open_p=Decimal("100"), high=Decimal("100"),
                low=Decimal("100"), close=Decimal("100"))
    session.commit()

    service = _service(session)
    service.update_results(as_of=date(2026, 5, 4))
    session.commit()

    pending_one = RecommendationResultRepository(session).get_by_recommendation_days(
        recommendation_id=rec.id, days_after=1,
    )
    assert pending_one.result_status == RESULT_STATUS_PENDING

    # Run 2: data arrives → +5% high → SUCCESS
    _seed_daily(session, symbol="005930", price_date=date(2026, 5, 5),
                open_p=Decimal("100"), high=Decimal("105"),
                low=Decimal("100"), close=Decimal("104"))
    session.commit()

    service.update_results(as_of=date(2026, 5, 25))
    session.commit()

    resolved = RecommendationResultRepository(session).get_by_recommendation_days(
        recommendation_id=rec.id, days_after=1,
    )
    assert resolved.id == pending_one.id  # same row, updated
    assert resolved.result_status == RESULT_STATUS_SUCCESS
    assert resolved.high_return == Decimal("5.0000")


# ---------- lookback_days ----------

def test_lookback_days_excludes_old_recommendations(session):
    # Old run outside lookback window; new run inside window
    old_run = RecommendationRunRepository(session).add(
        RecommendationRun(
            run_date=date(2026, 1, 1),
            started_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
            status="SUCCESS",
            telegram_sent=False,
        ),
    )
    new_run = RecommendationRunRepository(session).add(
        RecommendationRun(
            run_date=date(2026, 5, 1),
            started_at=datetime(2026, 5, 1, tzinfo=timezone.utc),
            status="SUCCESS",
            telegram_sent=False,
        ),
    )
    session.flush()
    RecommendationRepository(session).add(
        Recommendation(
            run_id=old_run.run_id, rank=1, market="KOSPI", symbol="000001",
            name="Old", grade="A", total_score=Decimal("80"),
        ),
    )
    new_rec = RecommendationRepository(session).add(
        Recommendation(
            run_id=new_run.run_id, rank=1, market="KOSPI", symbol="005930",
            name="New", grade="A", total_score=Decimal("80"),
        ),
    )
    session.commit()

    result = _service(session).update_results(
        as_of=date(2026, 5, 25),
        lookback_days=30,
    )
    session.commit()

    # Only the new recommendation is processed
    assert result.processed_recommendations == 1
    rows = RecommendationResultRepository(session).list()
    rec_ids = {r.recommendation_id for r in rows}
    assert rec_ids == {new_rec.id}


# ---------- empty registry ----------

def test_no_runs_returns_zero_counts(session):
    result = _service(session).update_results(as_of=date(2026, 5, 25))
    session.commit()
    assert result.processed_runs == 0
    assert result.processed_recommendations == 0
    assert result.upserted_results == 0
    assert RecommendationResultRepository(session).list() == []
