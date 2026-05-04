from datetime import date, datetime
from decimal import Decimal

import pytest
from sqlalchemy.exc import IntegrityError

from app.data.repositories import (
    DataSnapshotRepository,
    DecisionLogRepository,
    HoldingCheckRepository,
    JobRunRepository,
    MarketCapRankingRepository,
    MarketRegimeRepository,
    NewsItemRepository,
    NotificationLogRepository,
    RecommendationRepository,
    RecommendationResultRepository,
    RecommendationRunRepository,
    StockUniverseMemberRepository,
    StockUniverseRepository,
)
from app.db import Base
from app.db.models import (
    DataSnapshot,
    DecisionLog,
    HoldingCheck,
    JobRun,
    MarketCapRanking,
    MarketRegime,
    NewsItem,
    NotificationLog,
    Recommendation,
    RecommendationResult,
    RecommendationRun,
    StockUniverse,
    StockUniverseMember,
)
from app.db.session import create_db_engine, create_session_factory


@pytest.fixture()
def session():
    engine = create_db_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    session_factory = create_session_factory(engine)
    db_session = session_factory()
    try:
        yield db_session
    finally:
        db_session.close()
        Base.metadata.drop_all(engine)


def test_create_all_v01_required_tables(session):
    assert {
        "market_cap_rankings",
        "stock_universes",
        "stock_universe_members",
        "news_items",
        "market_regimes",
        "recommendation_runs",
        "recommendations",
        "recommendation_results",
        "holding_checks",
        "data_snapshots",
        "decision_logs",
        "notification_logs",
    }.issubset(set(Base.metadata.tables))


def test_market_cap_ranking_repository_and_unique_symbol_per_date_market(session):
    repository = MarketCapRankingRepository(session)
    rank_date = date(2026, 5, 4)

    repository.add(
        MarketCapRanking(
            rank_date=rank_date,
            market="KOSPI",
            rank=1,
            symbol="005930",
            name="Samsung Electronics",
            market_cap=Decimal("500000000000000"),
            is_analysis_target=True,
        ),
    )
    session.commit()

    rankings = repository.list_by_date_market(rank_date, "KOSPI")
    assert len(rankings) == 1
    assert rankings[0].symbol == "005930"

    with pytest.raises(IntegrityError):
        repository.add(
            MarketCapRanking(
                rank_date=rank_date,
                market="KOSPI",
                rank=2,
                symbol="005930",
                name="Samsung Electronics",
            ),
        )


def test_stock_universe_member_prevents_duplicate_symbol(session):
    universe_repository = StockUniverseRepository(session)
    member_repository = StockUniverseMemberRepository(session)

    universe = universe_repository.add(StockUniverse(name="MARKET_CAP_TOP_500"))
    session.commit()

    member_repository.add(StockUniverseMember(universe_id=universe.universe_id, symbol="005930"))
    session.commit()

    assert universe_repository.get_by_name("MARKET_CAP_TOP_500") is not None
    assert len(member_repository.list_by_universe(universe.universe_id)) == 1

    with pytest.raises(IntegrityError):
        member_repository.add(StockUniverseMember(universe_id=universe.universe_id, symbol="005930"))


def test_news_and_market_regime_repositories(session):
    news_repository = NewsItemRepository(session)
    regime_repository = MarketRegimeRepository(session)
    published_at = datetime(2026, 5, 4, 8, 30)

    news_repository.add(
        NewsItem(
            published_at=published_at,
            source="sample",
            title="Sample news",
            url="https://example.com/news/1",
            related_symbols=["005930"],
            sentiment="NEUTRAL",
        ),
    )
    regime_repository.add(
        MarketRegime(
            date=date(2026, 5, 4),
            market="KOSPI",
            regime="UPTREND_EARLY",
            market_score=Decimal("72"),
            risk_level="MEDIUM",
        ),
    )
    session.commit()

    assert len(news_repository.list_by_time_range(published_at, published_at)) == 1
    regime = regime_repository.get_by_date_market(date(2026, 5, 4), "KOSPI")
    assert regime is not None
    assert regime.regime == "UPTREND_EARLY"


def test_recommendation_run_recommendations_snapshot_and_results_relationship(session):
    snapshot_repository = DataSnapshotRepository(session)
    run_repository = RecommendationRunRepository(session)
    recommendation_repository = RecommendationRepository(session)
    result_repository = RecommendationResultRepository(session)

    snapshot = snapshot_repository.add(
        DataSnapshot(
            snapshot_time=datetime(2026, 5, 4, 6, 0),
            symbol="005930",
            snapshot_type="RECOMMENDATION",
            price_data_json={"close": 70500},
        ),
    )
    run = run_repository.add(
        RecommendationRun(
            run_date=date(2026, 5, 4),
            started_at=datetime(2026, 5, 4, 6, 0),
            status="SUCCESS",
            market_summary={"regime": "UPTREND_EARLY"},
        ),
    )
    recommendation = recommendation_repository.add(
        Recommendation(
            run_id=run.run_id,
            rank=1,
            market="KOSPI",
            symbol="005930",
            name="Samsung Electronics",
            grade="A",
            total_score=Decimal("82"),
            snapshot_id=snapshot.snapshot_id,
        ),
    )
    result_repository.add(
        RecommendationResult(
            recommendation_id=recommendation.id,
            result_date=date(2026, 5, 5),
            days_after=1,
            close_return=Decimal("1.2"),
            result_status="PARTIAL_SUCCESS",
        ),
    )
    session.commit()
    session.refresh(run)
    session.refresh(snapshot)

    assert run_repository.latest() is not None
    assert len(run.recommendations) == 1
    assert len(recommendation_repository.list_by_run_id(run.run_id)) == 1
    assert recommendation.snapshot == snapshot
    assert len(snapshot.recommendations) == 1
    assert len(result_repository.list_by_recommendation_id(recommendation.id)) == 1


def test_holding_check_and_decision_log_connect_to_data_snapshot(session):
    snapshot_repository = DataSnapshotRepository(session)
    holding_check_repository = HoldingCheckRepository(session)
    decision_log_repository = DecisionLogRepository(session)

    snapshot = snapshot_repository.add(
        DataSnapshot(
            snapshot_time=datetime(2026, 5, 4, 16, 30),
            symbol="005930",
            snapshot_type="HOLDING_CHECK",
            indicator_data_json={"ma20": 70000},
        ),
    )
    holding_check_repository.add(
        HoldingCheck(
            check_date=date(2026, 5, 4),
            check_type="POST_MARKET",
            symbol="005930",
            current_price=Decimal("70500"),
            total_score=Decimal("75"),
            decision="HOLD",
            snapshot_id=snapshot.snapshot_id,
        ),
    )
    decision_log_repository.add(
        DecisionLog(
            decision_type="HOLDING",
            symbol="005930",
            input_snapshot_id=snapshot.snapshot_id,
            rule_result_json={"score": 75},
            final_decision="HOLD",
            reason="No major damage",
        ),
    )
    session.commit()
    session.refresh(snapshot)

    checks = holding_check_repository.list_by_symbol("005930")
    logs = decision_log_repository.list_by_symbol("005930")

    assert checks[0].snapshot == snapshot
    assert logs[0].input_snapshot == snapshot
    assert len(snapshot.holding_checks) == 1
    assert len(snapshot.decision_logs) == 1


def test_notification_log_connects_to_job_run(session):
    job_repository = JobRunRepository(session)
    notification_repository = NotificationLogRepository(session)

    job = job_repository.add(
        JobRun(
            job_name="send_recommendation_report",
            started_at=datetime(2026, 5, 4, 6, 0),
            finished_at=datetime(2026, 5, 4, 6, 1),
            status="SUCCESS",
        ),
    )
    notification = notification_repository.add(
        NotificationLog(
            channel="TELEGRAM",
            message_type="REPORT",
            target="masked_chat",
            sent_at=datetime(2026, 5, 4, 6, 1),
            status="SUCCESS",
            related_job_id=job.job_id,
        ),
    )
    session.commit()
    session.refresh(job)

    logs = notification_repository.list_by_status("SUCCESS")

    assert logs[0].id == notification.id
    assert notification.related_job == job
    assert job.notification_logs[0].id == notification.id
