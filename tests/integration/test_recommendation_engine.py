from datetime import date
from decimal import Decimal

import pytest

from app.data.repositories import (
    DataSnapshotRepository,
    DecisionLogRepository,
    RecommendationRepository,
    RecommendationRunRepository,
    StockIndicatorRepository,
    StockRepository,
    StockUniverseMemberRepository,
    StockUniverseRepository,
)
from app.db import Base
from app.db.models import Stock, StockIndicator, StockUniverse, StockUniverseMember
from app.db.session import create_db_engine, create_session_factory
from app.decision.recommendation_engine import (
    RecommendationEngine,
    RecommendationRunResult,
)
from app.decision.risk_engine import (
    RISK_FLAG_BEARISH_MA_ALIGNMENT,
    RISK_FLAG_LOW_TECHNICAL_SCORE,
    RISK_FLAG_VOLUME_RATIO_MISSING,
    RISK_LEVEL_HIGH,
    RISK_LEVEL_LOW,
    RiskEngine,
)
from app.decision.scoring_engine import ScoringEngine


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


def _make_engine(session) -> RecommendationEngine:
    return RecommendationEngine(
        scoring_engine=ScoringEngine(),
        risk_engine=RiskEngine(),
        universe_repository=StockUniverseRepository(session),
        member_repository=StockUniverseMemberRepository(session),
        stock_repository=StockRepository(session),
        indicator_repository=StockIndicatorRepository(session),
        snapshot_repository=DataSnapshotRepository(session),
        run_repository=RecommendationRunRepository(session),
        recommendation_repository=RecommendationRepository(session),
        decision_log_repository=DecisionLogRepository(session),
    )


def _seed_universe(session, *, name: str = "MARKET_CAP_TOP_500") -> StockUniverse:
    universe = StockUniverseRepository(session).add(StockUniverse(name=name))
    session.flush()
    return universe


def _seed_stock_with_indicator(
    session,
    *,
    universe: StockUniverse | None,
    symbol: str,
    name: str,
    market: str = "KOSPI",
    sector: str = "전기전자",
    technical_score: Decimal | None = Decimal("70"),
    ma_alignment: str | None = "BULL",
    volume_ratio_20d: Decimal | None = Decimal("1.5"),
    indicator_date: date = date(2026, 5, 4),
    skip_indicator: bool = False,
) -> None:
    StockRepository(session).add(
        Stock(symbol=symbol, market=market, name=name, sector=sector),
    )
    if universe is not None:
        StockUniverseMemberRepository(session).add(
            StockUniverseMember(universe_id=universe.universe_id, symbol=symbol),
        )
    if not skip_indicator:
        StockIndicatorRepository(session).upsert(
            symbol=symbol,
            indicator_date=indicator_date,
            technical_score=technical_score,
            ma_alignment=ma_alignment,
            volume_ratio_20d=volume_ratio_20d,
        )
    session.flush()


# ---------- behavior ----------

def test_engine_creates_empty_run_when_universe_missing(session):
    engine = _make_engine(session)

    result = engine.generate(run_date=date(2026, 5, 4))
    session.commit()

    assert isinstance(result, RecommendationRunResult)
    assert result.status == "EMPTY"
    assert result.saved_count == 0
    assert result.candidate_count == 0

    runs = RecommendationRunRepository(session).list()
    assert len(runs) == 1
    assert runs[0].status == "EMPTY"
    assert runs[0].finished_at is not None
    assert runs[0].market_summary["universe_found"] is False
    assert runs[0].market_summary["phase"] == "5-3"


def test_engine_creates_empty_run_when_universe_has_no_members(session):
    _seed_universe(session)
    engine = _make_engine(session)

    result = engine.generate(run_date=date(2026, 5, 4))
    session.commit()

    assert result.status == "EMPTY"
    assert result.candidate_count == 0
    assert result.saved_count == 0

    recs = RecommendationRepository(session).list_by_run_id(result.run_id)
    assert recs == []


def test_engine_skips_symbols_without_indicators(session):
    universe = _seed_universe(session)
    _seed_stock_with_indicator(
        session, universe=universe, symbol="005930", name="삼성전자",
        technical_score=Decimal("80"),
    )
    _seed_stock_with_indicator(
        session, universe=universe, symbol="000660", name="SK하이닉스",
        skip_indicator=True,
    )
    engine = _make_engine(session)

    result = engine.generate(run_date=date(2026, 5, 4))
    session.commit()

    assert result.candidate_count == 1
    assert result.saved_count == 1
    assert result.skipped_no_indicator == 1

    saved = RecommendationRepository(session).list_by_run_id(result.run_id)
    assert [r.symbol for r in saved] == ["005930"]


def test_engine_generates_top_n_sorted_by_total_score_desc(session):
    universe = _seed_universe(session)
    seed = [
        ("AAA001", "Stock A", Decimal("90")),
        ("AAA002", "Stock B", Decimal("75")),
        ("AAA003", "Stock C", Decimal("60")),
        ("AAA004", "Stock D", Decimal("45")),
        ("AAA005", "Stock E", Decimal("30")),
        ("AAA006", "Stock F", Decimal("20")),
        ("AAA007", "Stock G", Decimal("10")),
    ]
    for symbol, name, tech in seed:
        _seed_stock_with_indicator(
            session, universe=universe, symbol=symbol, name=name,
            technical_score=tech,
        )
    engine = _make_engine(session)

    result = engine.generate(run_date=date(2026, 5, 4), top_n=5)
    session.commit()

    assert result.candidate_count == 7
    assert result.saved_count == 5
    assert result.status == "SUCCESS"

    saved = RecommendationRepository(session).list_by_run_id(result.run_id)
    assert [r.rank for r in saved] == [1, 2, 3, 4, 5]
    assert [r.symbol for r in saved] == ["AAA001", "AAA002", "AAA003", "AAA004", "AAA005"]
    # total_score includes technical plus neutral/rule-based dummy components.
    assert saved[0].total_score == Decimal("64.5000")
    assert saved[1].total_score == Decimal("59.2500")


def test_engine_grades_match_score_thresholds(session):
    universe = _seed_universe(session)
    _seed_stock_with_indicator(
        session, universe=universe, symbol="HIGH01", name="High",
        technical_score=Decimal("100"),
    )
    _seed_stock_with_indicator(
        session, universe=universe, symbol="MID001", name="Mid",
        technical_score=Decimal("50"),  # 50*0.35 = 17.5 -> D
    )
    _seed_stock_with_indicator(
        session, universe=universe, symbol="LOW001", name="Low",
        technical_score=Decimal("0"),  # 0 -> D
    )
    engine = _make_engine(session)

    result = engine.generate(run_date=date(2026, 5, 4), top_n=3)
    session.commit()

    saved = RecommendationRepository(session).list_by_run_id(result.run_id)
    by_symbol = {r.symbol: r for r in saved}
    assert by_symbol["HIGH01"].grade == "B"
    assert by_symbol["MID001"].grade == "C"
    assert by_symbol["LOW001"].grade == "D"


def test_engine_grade_uses_full_total_when_score_lifted_externally(session):
    """Smoke test: grade thresholds (S/A/B/C/D) read total_score directly."""
    from app.decision.recommendation_engine import _grade_for_score

    assert _grade_for_score(Decimal("90")) == "S"
    assert _grade_for_score(Decimal("85")) == "S"
    assert _grade_for_score(Decimal("84.9")) == "A"
    assert _grade_for_score(Decimal("70")) == "A"
    assert _grade_for_score(Decimal("55")) == "B"
    assert _grade_for_score(Decimal("40")) == "C"
    assert _grade_for_score(Decimal("39.99")) == "D"
    assert _grade_for_score(Decimal("0")) == "D"


def test_engine_persists_snapshot_recommendation_decision_log_linked(session):
    universe = _seed_universe(session)
    _seed_stock_with_indicator(
        session, universe=universe, symbol="005930", name="삼성전자",
        technical_score=Decimal("82"),
        ma_alignment="PERFECT_BULL",
        volume_ratio_20d=Decimal("2.1"),
    )
    engine = _make_engine(session)

    result = engine.generate(run_date=date(2026, 5, 4), top_n=5)
    session.commit()

    saved = RecommendationRepository(session).list_by_run_id(result.run_id)
    assert len(saved) == 1
    rec = saved[0]
    assert rec.snapshot_id is not None
    assert rec.market == "KOSPI"
    assert rec.name == "삼성전자"
    assert rec.technical_score == Decimal("82.0000")
    assert rec.news_score == Decimal("50.0000")
    assert rec.supply_score == Decimal("55.0000")
    assert rec.fundamental_score == Decimal("50.0000")
    assert rec.ai_score == Decimal("55.0000")
    assert rec.risk_score == Decimal("0.0000")
    assert "관찰 후보" in rec.reason
    assert "PERFECT_BULL" in rec.reason
    assert "Phase 5-3" in rec.risk_note
    assert "risk_level=LOW" in rec.risk_note
    assert rec.watch_condition is None
    assert rec.invalid_condition is None

    snapshot = DataSnapshotRepository(session).get(rec.snapshot_id)
    assert snapshot is not None
    assert snapshot.symbol == "005930"
    assert snapshot.snapshot_type == "RECOMMENDATION"
    assert snapshot.indicator_data_json["technical_score"] == "82.0000"
    assert snapshot.indicator_data_json["ma_alignment"] == "PERFECT_BULL"
    assert snapshot.market_context_json["run_id"] == result.run_id
    assert snapshot.market_context_json["phase"] == "5-3"
    assert snapshot.market_context_json["component_score_metadata"]["producer"] == (
        "DummyScoreProducer"
    )
    assert snapshot.market_context_json["risk_summary"] == {
        "level": RISK_LEVEL_LOW,
        "flags": [],
        "penalty": "0.0000",
    }

    logs = DecisionLogRepository(session).list_by_symbol("005930")
    assert len(logs) == 1
    log = logs[0]
    assert log.decision_type == "RECOMMENDATION"
    assert log.input_snapshot_id == rec.snapshot_id
    assert log.final_decision == "WATCH_CANDIDATE_RANK_1"
    assert log.rule_result_json["weighted_components"]["technical"] == "28.7000"
    assert log.rule_result_json["weighted_components"]["supply"] == "8.2500"
    assert log.rule_result_json["component_scores"] == {
        "news": "50",
        "supply": "55",
        "fundamental": "50",
        "ai": "55",
    }
    assert log.risk_result_json["alerts"] == []
    assert log.risk_result_json["risk_level"] == RISK_LEVEL_LOW
    assert log.risk_result_json["risk_penalty"] == "0.0000"
    assert log.risk_result_json["technical_score"] == "82.0000"
    assert log.risk_result_json["volume_ratio_20d"] == "2.1000"


def test_engine_records_run_metadata(session):
    universe = _seed_universe(session)
    _seed_stock_with_indicator(
        session, universe=universe, symbol="005930", name="삼성전자",
        technical_score=Decimal("60"),
    )
    _seed_stock_with_indicator(
        session, universe=universe, symbol="000660", name="SK하이닉스",
        skip_indicator=True,
    )
    engine = _make_engine(session)

    result = engine.generate(run_date=date(2026, 5, 4), top_n=5)
    session.commit()

    run = RecommendationRunRepository(session).get(result.run_id)
    assert run is not None
    assert run.run_date == date(2026, 5, 4)
    assert run.started_at is not None
    assert run.finished_at is not None
    assert run.status == "SUCCESS"
    assert run.telegram_sent is False
    assert run.market_summary == {
        "universe": "MARKET_CAP_TOP_500",
        "universe_found": True,
        "member_count": 2,
        "candidate_count": 1,
        "saved_count": 1,
        "skipped_no_indicator": 1,
        "skipped_no_stock_master": 0,
        "phase": "5-3",
        "score_components": ["news", "supply", "fundamental", "ai"],
        "score_producer": "DummyScoreProducer",
    }


def test_engine_two_runs_in_same_day_create_separate_run_ids(session):
    universe = _seed_universe(session)
    _seed_stock_with_indicator(
        session, universe=universe, symbol="005930", name="삼성전자",
        technical_score=Decimal("70"),
    )
    engine = _make_engine(session)

    first = engine.generate(run_date=date(2026, 5, 4), top_n=5)
    session.commit()
    second = engine.generate(run_date=date(2026, 5, 4), top_n=5)
    session.commit()

    assert first.run_id != second.run_id

    rec_repo = RecommendationRepository(session)
    assert len(rec_repo.list_by_run_id(first.run_id)) == 1
    assert len(rec_repo.list_by_run_id(second.run_id)) == 1


def test_engine_uses_custom_universe_name(session):
    custom = _seed_universe(session, name="KOSDAQ_TOP_200")
    _seed_stock_with_indicator(
        session, universe=custom, symbol="091990", name="셀트리온헬스케어",
        market="KOSDAQ", technical_score=Decimal("65"),
    )
    # Default universe absent should not produce candidates
    engine = _make_engine(session)

    result = engine.generate(
        run_date=date(2026, 5, 4),
        universe_name="KOSDAQ_TOP_200",
        top_n=5,
    )
    session.commit()

    assert result.saved_count == 1
    saved = RecommendationRepository(session).list_by_run_id(result.run_id)
    assert saved[0].symbol == "091990"
    assert saved[0].market == "KOSDAQ"

    run = RecommendationRunRepository(session).get(result.run_id)
    assert run.market_summary["universe"] == "KOSDAQ_TOP_200"


def test_engine_applies_risk_penalty_and_records_flags(session):
    universe = _seed_universe(session)
    _seed_stock_with_indicator(
        session, universe=universe, symbol="LOW001", name="Low Tech",
        technical_score=Decimal("10"),  # < 20 -> LOW_TECHNICAL_SCORE +10
        ma_alignment="BEAR",            # bearish -> BEARISH_MA_ALIGNMENT +8
        volume_ratio_20d=Decimal("1.0"),
    )
    engine = _make_engine(session)

    result = engine.generate(run_date=date(2026, 5, 4), top_n=5)
    session.commit()

    saved = RecommendationRepository(session).list_by_run_id(result.run_id)
    rec = saved[0]
    # weighted = 35.5 with dummy components; penalty = 18; final = 17.5
    assert rec.total_score == Decimal("17.5000")
    assert rec.risk_score == Decimal("18.0000")
    assert rec.grade == "D"

    log = DecisionLogRepository(session).list_by_symbol("LOW001")[0]
    assert set(log.risk_result_json["alerts"]) == {
        RISK_FLAG_LOW_TECHNICAL_SCORE,
        RISK_FLAG_BEARISH_MA_ALIGNMENT,
    }
    # 18 >= 15 -> HIGH
    assert log.risk_result_json["risk_level"] == RISK_LEVEL_HIGH
    assert log.risk_result_json["risk_penalty"] == "18.0000"

    snapshot = DataSnapshotRepository(session).get(rec.snapshot_id)
    assert snapshot.market_context_json["risk_summary"]["level"] == RISK_LEVEL_HIGH
    assert set(snapshot.market_context_json["risk_summary"]["flags"]) == {
        RISK_FLAG_LOW_TECHNICAL_SCORE,
        RISK_FLAG_BEARISH_MA_ALIGNMENT,
    }


def test_engine_records_volume_ratio_missing_flag(session):
    universe = _seed_universe(session)
    _seed_stock_with_indicator(
        session, universe=universe, symbol="VOL001", name="Vol Missing",
        technical_score=Decimal("60"),
        ma_alignment="BULL",
        volume_ratio_20d=None,
    )
    engine = _make_engine(session)

    result = engine.generate(run_date=date(2026, 5, 4), top_n=5)
    session.commit()

    log = DecisionLogRepository(session).list_by_symbol("VOL001")[0]
    assert RISK_FLAG_VOLUME_RATIO_MISSING in log.risk_result_json["alerts"]
    rec = RecommendationRepository(session).list_by_run_id(result.run_id)[0]
    assert rec.risk_score == Decimal("3.0000")  # PENALTY_VOLUME_MISSING


def test_engine_top_n_zero_yields_empty_run(session):
    universe = _seed_universe(session)
    _seed_stock_with_indicator(
        session, universe=universe, symbol="005930", name="삼성전자",
        technical_score=Decimal("80"),
    )
    engine = _make_engine(session)

    result = engine.generate(run_date=date(2026, 5, 4), top_n=0)
    session.commit()

    assert result.status == "EMPTY"
    assert result.candidate_count == 1
    assert result.saved_count == 0
    assert RecommendationRepository(session).list_by_run_id(result.run_id) == []
