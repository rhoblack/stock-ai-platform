from datetime import date
from decimal import Decimal

import pytest

from app.data.repositories import (
    AnalystReportRepository,
    DailyPriceRepository,
    DataSnapshotRepository,
    DecisionLogRepository,
    FundamentalSnapshotRepository,
    ReportConsensusSnapshotRepository,
    ReportScoreLogRepository,
    ReportSignalEventRepository,
    ReportThemeRepository,
    RecommendationRepository,
    RecommendationRunRepository,
    StockIndicatorRepository,
    StockRepository,
    StockUniverseMemberRepository,
    StockUniverseRepository,
    ThemeStockMappingRepository,
)
from app.analysis.score_producers import RealFundamentalScoreProducer
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


def _make_report_engine(session) -> RecommendationEngine:
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
        daily_price_repository=DailyPriceRepository(session),
        report_consensus_repository=ReportConsensusSnapshotRepository(session),
        theme_mapping_repository=ThemeStockMappingRepository(session),
        report_signal_event_repository=ReportSignalEventRepository(session),
        report_score_log_repository=ReportScoreLogRepository(session),
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


def _seed_latest_price(session, *, symbol: str, close: Decimal) -> None:
    DailyPriceRepository(session).upsert(
        symbol=symbol,
        price_date=date(2026, 5, 4),
        open_price=close,
        high_price=close,
        low_price=close,
        close_price=close,
        volume=1_000_000,
    )


def _seed_consensus(
    session,
    *,
    symbol: str,
    avg_target_price: Decimal,
    strong_buy_count: int = 0,
    buy_count: int = 0,
    hold_count: int = 0,
    sell_count: int = 0,
    strong_sell_count: int = 0,
) -> None:
    report_count = (
        strong_buy_count + buy_count + hold_count + sell_count + strong_sell_count
    )
    ReportConsensusSnapshotRepository(session).upsert_by_symbol_date_window(
        symbol=symbol,
        snapshot_date=date(2026, 5, 4),
        window_days=90,
        report_count=report_count,
        avg_target_price=avg_target_price,
        min_target_price=avg_target_price,
        max_target_price=avg_target_price,
        strong_buy_count=strong_buy_count,
        buy_count=buy_count,
        hold_count=hold_count,
        sell_count=sell_count,
        strong_sell_count=strong_sell_count,
        latest_published_at=date(2026, 5, 1),
    )


def _seed_theme_mapping(
    session,
    *,
    symbol: str,
    impact_direction: str,
    impact_strength: Decimal = Decimal("1.0"),
) -> None:
    report = AnalystReportRepository(session).create(
        broker_name="sample",
        published_at=date(2026, 5, 1),
        title=f"{symbol} theme",
        report_type="THEME",
        extraction_method="CSV_IMPORT",
        summary="theme summary",
    )
    theme = ReportThemeRepository(session).create(
        theme_name=f"{symbol} HBM",
        theme_category="SEMICONDUCTOR",
        direction="POSITIVE",
        time_horizon="MID",
        source_report_id=report.id,
        extraction_method="CSV_IMPORT",
    )
    ThemeStockMappingRepository(session).create(
        theme_id=theme.id,
        symbol=symbol,
        impact_direction=impact_direction,
        impact_strength=impact_strength,
        impact_path="DEMAND_RECOVERY",
        extraction_method="CSV_IMPORT",
        reason="theme mapping",
    )


def _seed_signal_event(
    session,
    *,
    symbol: str,
    event_type: str,
    direction: str,
    strength: Decimal = Decimal("1.0"),
) -> None:
    report = AnalystReportRepository(session).create(
        broker_name="signal",
        published_at=date(2026, 5, 1),
        title=f"{symbol} signal {event_type}",
        report_type="COMPANY",
        extraction_method="CSV_IMPORT",
        symbol=symbol,
        summary="signal summary",
    )
    ReportSignalEventRepository(session).create(
        report_id=report.id,
        symbol=symbol,
        event_type=event_type,
        direction=direction,
        strength=strength,
        time_horizon="SHORT",
        extraction_method="CSV_IMPORT",
        summary="signal event",
    )


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


def test_engine_applies_report_score_positive_adjustment(session):
    universe = _seed_universe(session)
    _seed_stock_with_indicator(
        session, universe=universe, symbol="005930", name="Samsung",
        technical_score=Decimal("80"),
    )
    _seed_latest_price(session, symbol="005930", close=Decimal("100"))
    _seed_consensus(
        session,
        symbol="005930",
        avg_target_price=Decimal("160"),
        strong_buy_count=1,
    )
    engine = _make_report_engine(session)

    result = engine.generate(run_date=date(2026, 5, 4), top_n=5)
    session.commit()

    rec = RecommendationRepository(session).list_by_run_id(result.run_id)[0]
    log = DecisionLogRepository(session).list_by_symbol("005930")[0]
    evidence = log.rule_result_json["report_evidence"]
    assert Decimal(log.rule_result_json["total_score_after"]) > Decimal(
        log.rule_result_json["base_total_score"],
    )
    assert rec.total_score == Decimal(log.rule_result_json["total_score_after"])
    assert evidence["report_score"] == "100.00"
    assert evidence["report_score_adjustment"] == "5.00"


def test_engine_applies_theme_signal_positive_adjustment(session):
    universe = _seed_universe(session)
    _seed_stock_with_indicator(
        session, universe=universe, symbol="005930", name="Samsung",
        technical_score=Decimal("80"),
    )
    _seed_latest_price(session, symbol="005930", close=Decimal("100"))
    _seed_theme_mapping(session, symbol="005930", impact_direction="POSITIVE")
    _seed_signal_event(
        session,
        symbol="005930",
        event_type="TARGET_PRICE_UP",
        direction="POSITIVE",
    )
    engine = _make_report_engine(session)

    result = engine.generate(run_date=date(2026, 5, 4), top_n=5)
    session.commit()

    log = DecisionLogRepository(session).list_by_symbol("005930")[0]
    evidence = log.rule_result_json["report_evidence"]
    assert evidence["theme_signal_score"] == "70.00"
    assert evidence["theme_signal_adjustment"] == "2.00"
    assert evidence["theme_count"] == 1
    assert evidence["signal_event_count"] == 1
    assert evidence["top_themes"][0]["theme_name"] == "005930 HBM"
    assert evidence["top_events"][0]["event_type"] == "TARGET_PRICE_UP"


def test_engine_negative_risk_signal_reduces_total_score(session):
    universe = _seed_universe(session)
    _seed_stock_with_indicator(
        session, universe=universe, symbol="005930", name="Samsung",
        technical_score=Decimal("80"),
    )
    _seed_latest_price(session, symbol="005930", close=Decimal("100"))
    _seed_signal_event(
        session,
        symbol="005930",
        event_type="RISK_WARNING",
        direction="NEGATIVE",
    )
    engine = _make_report_engine(session)

    result = engine.generate(run_date=date(2026, 5, 4), top_n=5)
    session.commit()

    log = DecisionLogRepository(session).list_by_symbol("005930")[0]
    evidence = log.rule_result_json["report_evidence"]
    assert evidence["theme_signal_score"] == "37.50"
    assert evidence["theme_signal_adjustment"] == "-1.25"
    assert Decimal(log.rule_result_json["total_score_after"]) < Decimal(
        log.rule_result_json["base_total_score"],
    )


def test_engine_persists_report_score_log(session):
    universe = _seed_universe(session)
    _seed_stock_with_indicator(
        session, universe=universe, symbol="005930", name="Samsung",
        technical_score=Decimal("80"),
    )
    _seed_latest_price(session, symbol="005930", close=Decimal("100"))
    _seed_consensus(
        session,
        symbol="005930",
        avg_target_price=Decimal("120"),
        buy_count=1,
    )
    _seed_theme_mapping(session, symbol="005930", impact_direction="POSITIVE")
    engine = _make_report_engine(session)

    result = engine.generate(run_date=date(2026, 5, 4), top_n=5)
    session.commit()

    rows = ReportScoreLogRepository(session).list_by_recommendation_run(result.run_id)
    assert len(rows) == 1
    assert rows[0].symbol == "005930"
    assert rows[0].report_score == Decimal("75.00")
    assert rows[0].theme_signal_score == Decimal("60.00")
    assert rows[0].evidence_json["report_score"] == "75.00"


def test_engine_report_integration_keeps_candidate_generation_flow(session):
    universe = _seed_universe(session)
    _seed_stock_with_indicator(
        session, universe=universe, symbol="005930", name="Samsung",
        technical_score=Decimal("80"),
    )
    _seed_stock_with_indicator(
        session, universe=universe, symbol="000660", name="Hynix",
        technical_score=Decimal("70"),
    )
    engine = _make_report_engine(session)

    result = engine.generate(run_date=date(2026, 5, 4), top_n=5)
    session.commit()

    assert result.status == "SUCCESS"
    assert result.candidate_count == 2
    assert result.saved_count == 2
    assert len(RecommendationRepository(session).list_by_run_id(result.run_id)) == 2
    assert len(ReportScoreLogRepository(session).list_by_recommendation_run(result.run_id)) == 2


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


# ---------------------------------------------------------------------------
# v0.5 Phase C — RealNewsScoreProducer + DisclosureRiskProducer integration
# ---------------------------------------------------------------------------


def _make_engine_with_news_and_disclosure(
    session,
    *,
    now,
):
    """Engine wired with RealNewsScoreProducer + DisclosureRiskProducer."""
    from app.analysis.score_producers import (
        DisclosureRiskProducer,
        RealNewsScoreProducer,
    )
    from app.data.repositories import NewsItemRepository

    news_repo = NewsItemRepository(session)
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
        score_producer=RealNewsScoreProducer(news_repo, now=now),
        disclosure_risk_producer=DisclosureRiskProducer(news_repo, now=now),
    )


def test_engine_uses_real_news_score_when_news_present(session):
    """RealNewsScoreProducer 가 주입되면 placeholder 50 대신 실 news_score 가 반영된다."""
    from datetime import datetime as _dt
    from datetime import timezone as _tz

    universe = _seed_universe(session)
    _seed_stock_with_indicator(
        session, universe=universe, symbol="005930", name="삼성전자",
        technical_score=Decimal("70"),
    )
    # Seed 1 POSITIVE news within ≤24h
    from app.data.repositories import NewsItemRepository

    NewsItemRepository(session).upsert_by_url(
        url="https://example.com/news/005930/positive",
        published_at=_dt(2026, 5, 4, 0, 0, tzinfo=_tz.utc),
        source="UnitTest",
        title="positive news",
        related_symbols=["005930"],
        sentiment="POSITIVE",
        category="NEWS",
    )
    session.commit()

    engine = _make_engine_with_news_and_disclosure(
        session, now=_dt(2026, 5, 4, 12, 0, tzinfo=_tz.utc),
    )
    result = engine.generate(run_date=date(2026, 5, 4))
    session.commit()
    assert result.saved_count == 1

    rec = RecommendationRepository(session).list_by_run_id(result.run_id)[0]
    # 50 + 1.0 * 5 / 1 = 55 (POSITIVE 1, recency 1.0)
    assert rec.news_score == Decimal("55.0000")


def test_engine_records_news_evidence_in_decision_log(session):
    """decision_logs.rule_result_json["news_evidence"] 필드가 채워진다."""
    from datetime import datetime as _dt
    from datetime import timezone as _tz

    universe = _seed_universe(session)
    _seed_stock_with_indicator(
        session, universe=universe, symbol="005930", name="삼성전자",
        technical_score=Decimal("70"),
    )
    from app.data.repositories import NewsItemRepository

    NewsItemRepository(session).upsert_by_url(
        url="https://example.com/news/005930/p",
        published_at=_dt(2026, 5, 4, 0, 0, tzinfo=_tz.utc),
        source="W1",
        title="positive headline",
        related_symbols=["005930"],
        sentiment="POSITIVE",
        category="NEWS",
    )
    session.commit()

    engine = _make_engine_with_news_and_disclosure(
        session, now=_dt(2026, 5, 4, 12, 0, tzinfo=_tz.utc),
    )
    result = engine.generate(run_date=date(2026, 5, 4))
    session.commit()

    log = DecisionLogRepository(session).list_by_symbol("005930")[0]
    news_ev = log.rule_result_json["news_evidence"]
    assert news_ev["news_count"] == 1
    assert news_ev["positive_count"] == 1
    assert news_ev["top_news"][0]["title"] == "positive headline"
    # Safe-fields-only — no body/content/full_text
    assert set(news_ev["top_news"][0].keys()) == {
        "title", "url", "provider", "published_at", "sentiment",
    }


def test_engine_records_disclosure_risk_evidence_and_flag(session):
    """RISK_DISCLOSURE 가 14일 이내에 발견되면 flag 추가 + penalty 가산 + evidence 기록."""
    from datetime import datetime as _dt
    from datetime import timezone as _tz

    universe = _seed_universe(session)
    _seed_stock_with_indicator(
        session, universe=universe, symbol="005930", name="삼성전자",
        technical_score=Decimal("70"),
    )
    from app.data.repositories import NewsItemRepository

    repo = NewsItemRepository(session)
    repo.upsert_by_url(
        url="https://example.com/disc/005930/halt",
        published_at=_dt(2026, 5, 2, 0, 0, tzinfo=_tz.utc),
        source="DART",
        title="거래정지",
        related_symbols=["005930"],
        sentiment="NEGATIVE",
        category="RISK_DISCLOSURE",
    )
    session.commit()

    engine = _make_engine_with_news_and_disclosure(
        session, now=_dt(2026, 5, 4, 12, 0, tzinfo=_tz.utc),
    )
    result = engine.generate(run_date=date(2026, 5, 4))
    session.commit()

    rec = RecommendationRepository(session).list_by_run_id(result.run_id)[0]
    assert rec.risk_score == Decimal("3.0000")  # 1 disclosure × 3

    log = DecisionLogRepository(session).list_by_symbol("005930")[0]
    assert "RISK_DISCLOSURE" in log.risk_result_json["alerts"]
    disc_ev = log.rule_result_json["disclosure_risk_evidence"]
    assert disc_ev["risk_disclosure_count"] == 1
    assert disc_ev["recent_risk_disclosures"][0]["title"] == "거래정지"


def test_engine_no_news_no_disclosure_keeps_default_dummy_behavior(session):
    """RealNewsScoreProducer 주입했지만 news_items 비어 있으면 placeholder 50 유지."""
    from datetime import datetime as _dt
    from datetime import timezone as _tz

    universe = _seed_universe(session)
    _seed_stock_with_indicator(
        session, universe=universe, symbol="005930", name="삼성전자",
        technical_score=Decimal("70"),
    )

    engine = _make_engine_with_news_and_disclosure(
        session, now=_dt(2026, 5, 4, 12, 0, tzinfo=_tz.utc),
    )
    result = engine.generate(run_date=date(2026, 5, 4))
    session.commit()

    rec = RecommendationRepository(session).list_by_run_id(result.run_id)[0]
    assert rec.news_score == Decimal("50.0000")  # neutral fallback
    log = DecisionLogRepository(session).list_by_symbol("005930")[0]
    # disclosure_risk_evidence is recorded (count=0) since producer was injected
    assert log.rule_result_json["disclosure_risk_evidence"]["risk_disclosure_count"] == 0
    # No RISK_DISCLOSURE flag
    assert "RISK_DISCLOSURE" not in log.risk_result_json["alerts"]


def test_engine_dummy_only_does_not_emit_evidence(session):
    """Backward compat: DummyScoreProducer-only 주입 시 evidence 필드는 None."""
    universe = _seed_universe(session)
    _seed_stock_with_indicator(
        session, universe=universe, symbol="005930", name="삼성전자",
        technical_score=Decimal("70"),
    )

    engine = _make_engine(session)  # default DummyScoreProducer, no disclosure producer
    result = engine.generate(run_date=date(2026, 5, 4))
    session.commit()

    log = DecisionLogRepository(session).list_by_symbol("005930")[0]
    # evidence keys exist but are None (or absent — both acceptable; we set None)
    assert log.rule_result_json.get("news_evidence") is None
    assert log.rule_result_json.get("disclosure_risk_evidence") is None
    # No RISK_DISCLOSURE flag, existing risk flags work as before
    assert "RISK_DISCLOSURE" not in log.risk_result_json["alerts"]


def test_real_fundamental_score_integrates_with_snapshot_and_decision_log(session):
    universe = _seed_universe(session)
    _seed_stock_with_indicator(
        session,
        universe=universe,
        symbol="005930",
        name="Samsung",
        technical_score=Decimal("70"),
    )
    FundamentalSnapshotRepository(session).upsert_by_symbol_period(
        symbol="005930",
        snapshot_date=date(2026, 5, 1),
        fiscal_year=2025,
        fiscal_quarter=4,
        per=Decimal("10"),
        pbr=Decimal("1.0"),
        roe=Decimal("18"),
        debt_ratio=Decimal("40"),
        revenue_growth_yoy=Decimal("15"),
        operating_income_growth_yoy=Decimal("20"),
        dividend_yield=Decimal("2"),
        source="TEST",
    )
    engine = RecommendationEngine(
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
        score_producer=RealFundamentalScoreProducer(FundamentalSnapshotRepository(session)),
    )

    result = engine.generate(run_date=date(2026, 5, 4), top_n=1)
    session.commit()

    rec = RecommendationRepository(session).list_by_run_id(result.run_id)[0]
    assert rec.fundamental_score > Decimal("50")
    log = DecisionLogRepository(session).list_by_symbol("005930")[0]
    evidence = log.rule_result_json["fundamental_evidence"]
    assert evidence["snapshot_date"] == "2026-05-01"
    assert "source" not in evidence
    assert "source_file_path" not in evidence
    snapshot = DataSnapshotRepository(session).get(rec.snapshot_id)
    assert snapshot.market_context_json["fundamental_evidence"] == evidence


def test_scoring_engine_recommendation_weights_unchanged():
    from app.decision.scoring_engine import NewRecommendationScoreInputs

    scoring = ScoringEngine()
    result = scoring.score_new_recommendation(
        NewRecommendationScoreInputs(
            technical_score=Decimal("100"),
            news_score=Decimal("100"),
            supply_score=Decimal("100"),
            fundamental_score=Decimal("100"),
            ai_score=Decimal("100"),
            risk_penalty=Decimal("0"),
        ),
    )
    assert result.weighted_components == {
        "technical": Decimal("35.0000"),
        "news": Decimal("25.0000"),
        "supply": Decimal("15.0000"),
        "fundamental": Decimal("15.0000"),
        "ai": Decimal("10.0000"),
    }
