from datetime import date
from decimal import Decimal

import pytest

from app.analysis.score_producers import (
    RealEarningsScoreProducer,
    RealFundamentalScoreProducer,
)
from app.data.repositories import EarningsEventRepository, FundamentalSnapshotRepository
from app.db import Base
from app.db.models import Holding, Stock, StockIndicator
from app.db.session import create_db_engine, create_session_factory


@pytest.fixture()
def session():
    engine = create_db_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    factory = create_session_factory(engine)
    db_session = factory()
    try:
        yield db_session
    finally:
        db_session.close()
        Base.metadata.drop_all(engine)


def _stock(symbol: str = "005930") -> Stock:
    return Stock(symbol=symbol, market="KOSPI", name="sample")


def _indicator() -> StockIndicator:
    return StockIndicator(symbol="005930", date=date(2026, 5, 4), technical_score=Decimal("70"))


def _holding(symbol: str = "005930") -> Holding:
    return Holding(symbol=symbol, quantity=Decimal("1"), avg_buy_price=Decimal("100"))


def _upsert_fundamental(session, **overrides):
    values = {
        "symbol": "005930",
        "snapshot_date": date(2026, 5, 1),
        "fiscal_year": 2025,
        "fiscal_quarter": 4,
        "per": Decimal("10"),
        "pbr": Decimal("1.0"),
        "roe": Decimal("18"),
        "debt_ratio": Decimal("40"),
        "revenue_growth_yoy": Decimal("15"),
        "operating_income_growth_yoy": Decimal("20"),
        "dividend_yield": Decimal("2.0"),
        "source": "TEST",
    }
    values.update(overrides)
    return FundamentalSnapshotRepository(session).upsert_by_symbol_period(**values)


def _upsert_earnings(session, **overrides):
    values = {
        "symbol": "005930",
        "event_date": date(2026, 5, 1),
        "fiscal_year": 2026,
        "fiscal_quarter": 1,
        "event_type": "FINAL",
        "operating_income_actual": Decimal("110"),
        "operating_income_consensus": Decimal("100"),
        "surprise_type": "BEAT",
        "surprise_pct": Decimal("10"),
        "source": "TEST",
    }
    values.update(overrides)
    return EarningsEventRepository(session).upsert_by_symbol_event(**values)


def test_real_fundamental_no_snapshot_returns_50_and_safe_evidence(session):
    producer = RealFundamentalScoreProducer(FundamentalSnapshotRepository(session))
    scores = producer.score_recommendation(stock=_stock(), indicator=_indicator())
    assert scores.fundamental_score == Decimal("50")
    assert scores.metadata["fundamental_evidence"] == {"reason": "no_fundamental_snapshot"}


def test_real_fundamental_good_snapshot_scores_above_50(session):
    _upsert_fundamental(session)
    producer = RealFundamentalScoreProducer(FundamentalSnapshotRepository(session))
    scores = producer.score_recommendation(stock=_stock(), indicator=_indicator())
    assert scores.fundamental_score > Decimal("50")
    evidence = scores.metadata["fundamental_evidence"]
    assert evidence["snapshot_date"] == "2026-05-01"
    assert "source" not in evidence
    assert "source_file_path" not in evidence


def test_real_fundamental_bad_snapshot_scores_below_50_and_debt_penalty(session):
    _upsert_fundamental(
        session,
        per=Decimal("80"),
        pbr=Decimal("6"),
        roe=Decimal("-5"),
        debt_ratio=Decimal("250"),
        revenue_growth_yoy=Decimal("-10"),
        operating_income_growth_yoy=Decimal("-20"),
        dividend_yield=Decimal("0"),
    )
    producer = RealFundamentalScoreProducer(FundamentalSnapshotRepository(session))
    scores = producer.score_recommendation(stock=_stock(), indicator=_indicator())
    assert scores.fundamental_score < Decimal("50")


def test_real_fundamental_growth_adds_and_score_clamps(session):
    _upsert_fundamental(
        session,
        per=Decimal("1"),
        pbr=Decimal("0.5"),
        roe=Decimal("200"),
        debt_ratio=Decimal("1"),
        revenue_growth_yoy=Decimal("300"),
        operating_income_growth_yoy=Decimal("300"),
        dividend_yield=Decimal("20"),
    )
    producer = RealFundamentalScoreProducer(FundamentalSnapshotRepository(session))
    scores = producer.score_recommendation(stock=_stock(), indicator=_indicator())
    assert Decimal("0") <= scores.fundamental_score <= Decimal("100")
    assert scores.fundamental_score > Decimal("70")


def test_real_earnings_no_event_returns_50_and_safe_evidence(session):
    producer = RealEarningsScoreProducer(EarningsEventRepository(session), as_of=date(2026, 5, 5))
    scores = producer.score_holding(holding=_holding(), indicator=_indicator())
    assert scores.earnings_score == Decimal("50")
    assert scores.metadata["earnings_evidence"] == {"reason": "no_earnings_event"}


def test_real_earnings_beat_miss_meet_unknown_scores(session):
    producer = RealEarningsScoreProducer(EarningsEventRepository(session), as_of=date(2026, 5, 5))
    _upsert_earnings(session, surprise_type="BEAT", surprise_pct=Decimal("20"))
    assert producer.score_holding(holding=_holding(), indicator=_indicator()).earnings_score > Decimal("50")

    _upsert_earnings(session, symbol="000660", surprise_type="MISS", surprise_pct=Decimal("-20"))
    assert producer.score_holding(holding=_holding("000660"), indicator=_indicator()).earnings_score < Decimal("50")

    _upsert_earnings(session, symbol="035420", surprise_type="MEET", surprise_pct=Decimal("1"))
    meet = producer.score_holding(holding=_holding("035420"), indicator=_indicator()).earnings_score
    assert Decimal("49") <= meet <= Decimal("51")

    _upsert_earnings(session, symbol="005380", event_date=date(2026, 5, 20), surprise_type="UNKNOWN", surprise_pct=None)
    unknown = producer.score_holding(holding=_holding("005380"), indicator=_indicator()).earnings_score
    assert unknown == Decimal("50.0")


def test_real_earnings_surprise_cap_and_old_event_decay(session):
    _upsert_earnings(session, surprise_type="BEAT", surprise_pct=Decimal("1000"))
    producer = RealEarningsScoreProducer(EarningsEventRepository(session), as_of=date(2026, 5, 5))
    fresh = producer.score_holding(holding=_holding(), indicator=_indicator()).earnings_score
    assert fresh == Decimal("70.0")

    _upsert_earnings(session, symbol="000660", event_date=date(2025, 12, 1), surprise_type="BEAT", surprise_pct=Decimal("1000"))
    old = producer.score_holding(holding=_holding("000660"), indicator=_indicator()).earnings_score
    assert old < fresh
    assert old > Decimal("50")


def test_real_earnings_evidence_safe_fields_only(session):
    _upsert_earnings(session)
    producer = RealEarningsScoreProducer(EarningsEventRepository(session), as_of=date(2026, 5, 5))
    scores = producer.score_holding(holding=_holding(), indicator=_indicator())
    evidence = scores.metadata["earnings_evidence"]
    assert evidence["latest_event_date"] == "2026-05-01"
    assert "source" not in evidence
    assert "source_file_path" not in evidence
    assert "memo" not in evidence
