from datetime import date, datetime, timezone
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool

from app.config.settings import Settings, get_settings
from app.data.repositories import (
    DailyPriceRepository,
    DataSnapshotRepository,
    DecisionLogRepository,
    HoldingCheckRepository,
    HoldingRepository,
    JobRunRepository,
    MarketCapRankingRepository,
    MarketRegimeRepository,
    NewsItemRepository,
    NotificationLogRepository,
    RecommendationRepository,
    RecommendationResultRepository,
    RecommendationRunRepository,
    StockIndicatorRepository,
    StockRepository,
    StockUniverseMemberRepository,
    StockUniverseRepository,
)
from app.db import Base
from app.db.models import (
    DailyPrice,
    DataSnapshot,
    Holding,
    HoldingCheck,
    JobRun,
    MarketCapRanking,
    MarketRegime,
    NewsItem,
    Recommendation,
    RecommendationResult,
    RecommendationRun,
    Stock,
    StockIndicator,
    StockUniverse,
    StockUniverseMember,
)
from app.db.session import create_session_factory, get_session


@pytest.fixture()
def session():
    # FastAPI TestClient runs sync routes in a thread pool worker, which would
    # get a fresh in-memory SQLite connection (and therefore no tables) under
    # the default pool. Force a single shared connection via StaticPool.
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )
    Base.metadata.create_all(engine)
    factory = create_session_factory(engine)
    db_session = factory()
    try:
        yield db_session
    finally:
        db_session.close()
        Base.metadata.drop_all(engine)


@pytest.fixture()
def client(session):
    from app.main import app

    def override_session():
        yield session

    def override_settings():
        return Settings(
            app_env="test",
            app_name="stock_ai_platform",
            timezone="Asia/Seoul",
            log_level="INFO",
            telegram_enabled=False,
            telegram_bot_token="abcd1234efgh5678",
            telegram_chat_id="123456789012",
            telegram_api_base_url="https://mock-telegram.local",
            telegram_timeout_seconds=5,
            kis_app_key="kkkk1111kkkk2222",
            kis_app_secret="ssss3333ssss4444",
            kis_account_no="9876543210",
            kis_account_product_code="01",
            kis_use_paper=True,
            scheduler_enabled=False,
            feature_real_order_execution=False,
            feature_full_auto=False,
            feature_paper_trading=False,
            feature_backtest=False,
            feature_custom_ai_training=False,
        )

    app.dependency_overrides[get_session] = override_session
    app.dependency_overrides[get_settings] = override_settings
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()


# ---------- seeders ----------

def _seed_stock(session, *, symbol: str, name: str, market: str = "KOSPI",
                sector: str = "전기전자") -> Stock:
    stock = StockRepository(session).add(
        Stock(symbol=symbol, name=name, market=market, sector=sector),
    )
    session.flush()
    return stock


def _seed_daily_price(session, *, symbol: str, price_date: date,
                      close: Decimal = Decimal("100")) -> DailyPrice:
    return DailyPriceRepository(session).upsert(
        symbol=symbol,
        price_date=price_date,
        open_price=close,
        high_price=close,
        low_price=close,
        close_price=close,
        volume=1_000_000,
    )


def _seed_indicator(session, *, symbol: str, indicator_date: date,
                    technical_score: Decimal = Decimal("80"),
                    ma20: Decimal | None = Decimal("95"),
                    ma_alignment: str | None = "BULL") -> StockIndicator:
    return StockIndicatorRepository(session).upsert(
        symbol=symbol,
        indicator_date=indicator_date,
        ma20=ma20,
        ma_alignment=ma_alignment,
        technical_score=technical_score,
        volume_ratio_20d=Decimal("1.5"),
    )


def _seed_full_dataset(session) -> dict:
    """Seed enough rows to drive every endpoint at least once."""
    today = date(2026, 5, 4)

    samsung = _seed_stock(session, symbol="005930", name="삼성전자")
    sk_hynix = _seed_stock(session, symbol="000660", name="SK하이닉스")
    _seed_daily_price(session, symbol="005930", price_date=today,
                      close=Decimal("70500"))
    _seed_indicator(session, symbol="005930", indicator_date=today,
                    technical_score=Decimal("82"), ma20=Decimal("70000"),
                    ma_alignment="PERFECT_BULL")
    _seed_indicator(session, symbol="000660", indicator_date=today,
                    technical_score=Decimal("60"), ma20=Decimal("160000"))

    holding = HoldingRepository(session).add(
        Holding(
            symbol="005930",
            quantity=Decimal("10"),
            avg_buy_price=Decimal("70000"),
            is_active=True,
            strategy_type="장기",
        ),
    )
    session.flush()

    universe = StockUniverseRepository(session).add(
        StockUniverse(name="MARKET_CAP_TOP_500"),
    )
    session.flush()
    StockUniverseMemberRepository(session).add(
        StockUniverseMember(universe_id=universe.universe_id, symbol="005930"),
    )

    MarketCapRankingRepository(session).add(
        MarketCapRanking(
            rank_date=today, market="KOSPI", rank=1, symbol="005930",
            name="삼성전자", market_cap=Decimal("500000000000000"),
            close_price=Decimal("70500"), sector="전기전자",
            is_analysis_target=True,
        ),
    )

    MarketRegimeRepository(session).add(
        MarketRegime(
            date=today, market="KOSPI", regime="UPTREND_EARLY",
            market_score=Decimal("72"), risk_level="MEDIUM",
            reason="상승 초기",
        ),
    )

    NewsItemRepository(session).add(
        NewsItem(
            published_at=datetime(2026, 5, 4, 8, 0),
            source="sample",
            title="HBM 수요 강세",
            url="https://example.com/n/1",
            related_symbols=["005930"],
            sentiment="POSITIVE",
            theme="반도체",
        ),
    )

    JobRunRepository(session).add(
        JobRun(
            job_name="collect_close_data",
            started_at=datetime(2026, 5, 4, 18, 0),
            finished_at=datetime(2026, 5, 4, 18, 1),
            status="SUCCESS",
            result_summary={"rows": 500},
        ),
    )

    snapshot_rec = DataSnapshotRepository(session).add(
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
    snapshot_check = DataSnapshotRepository(session).add(
        DataSnapshot(
            snapshot_time=datetime(2026, 5, 4, 8, 30, tzinfo=timezone.utc),
            symbol="005930",
            snapshot_type="HOLDING_CHECK",
            indicator_data_json={"ma20": "70000"},
            market_context_json={
                "check_date": "2026-05-04",
                "check_type": "PRE_MARKET",
                "phase": "5-3",
                "risk_summary": {
                    "level": "HIGH",
                    "flags": ["MA20_BREAKDOWN", "STOP_LOSS_NEAR"],
                    "penalty": "23.0000",
                },
            },
        ),
    )
    session.flush()

    run = RecommendationRunRepository(session).add(
        RecommendationRun(
            run_date=today,
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

    rec = RecommendationRepository(session).add(
        Recommendation(
            run_id=run.run_id,
            rank=1,
            market="KOSPI",
            symbol="005930",
            name="삼성전자",
            grade="A",
            total_score=Decimal("82"),
            technical_score=Decimal("82"),
            news_score=Decimal("50"),
            supply_score=Decimal("55"),
            fundamental_score=Decimal("50"),
            ai_score=Decimal("55"),
            risk_score=Decimal("0.0000"),
            reason="관찰 후보 · 기술점수 82",
            risk_note="Phase 5-3 placeholder",
            snapshot_id=snapshot_rec.snapshot_id,
        ),
    )
    session.flush()

    # Seed 1/3/5/20-day results for the recommendation
    result_repo = RecommendationResultRepository(session)
    result_repo.upsert(
        recommendation_id=rec.id, days_after=1,
        result_date=date(2026, 5, 5),
        open_return=Decimal("0.5000"), high_return=Decimal("2.0000"),
        low_return=Decimal("-0.5000"), close_return=Decimal("1.5000"),
        max_return=Decimal("2.0000"), max_drawdown=Decimal("-0.5000"),
        result_status="SUCCESS",
    )
    result_repo.upsert(
        recommendation_id=rec.id, days_after=3,
        result_date=date(2026, 5, 7),
        open_return=Decimal("1.0000"), high_return=Decimal("3.5000"),
        low_return=Decimal("-1.0000"), close_return=Decimal("2.5000"),
        max_return=Decimal("3.5000"), max_drawdown=Decimal("-1.0000"),
        result_status="SUCCESS",
    )
    result_repo.upsert(
        recommendation_id=rec.id, days_after=5,
        result_date=date(2026, 5, 9),
        open_return=Decimal("1.5000"), high_return=Decimal("4.0000"),
        low_return=Decimal("-2.0000"), close_return=Decimal("3.0000"),
        max_return=Decimal("4.0000"), max_drawdown=Decimal("-2.0000"),
        result_status="SUCCESS",
    )
    result_repo.upsert(
        recommendation_id=rec.id, days_after=20,
        result_date=date(2026, 5, 24),
        open_return=None, high_return=None,
        low_return=None, close_return=None,
        max_return=None, max_drawdown=None,
        result_status="PENDING",
    )
    session.flush()

    holding_check = HoldingCheckRepository(session).add(
        HoldingCheck(
            check_date=today,
            check_type="PRE_MARKET",
            symbol="005930",
            current_price=Decimal("65000"),
            avg_buy_price=Decimal("70000"),
            return_rate=Decimal("-7.1429"),
            technical_score=Decimal("60"),
            risk_score=Decimal("23.0000"),
            total_score=Decimal("0"),
            grade="D",
            decision="SELL_REVIEW",
            reason="매도 검토 · 위험: 20일선 이탈, 손절 근접",
            alert=True,
            snapshot_id=snapshot_check.snapshot_id,
        ),
    )
    session.flush()
    session.commit()

    return {
        "today": today,
        "stock_samsung": samsung,
        "stock_sk_hynix": sk_hynix,
        "holding": holding,
        "universe": universe,
        "run": run,
        "recommendation": rec,
        "holding_check": holding_check,
        "snapshot_rec_id": snapshot_rec.snapshot_id,
        "snapshot_check_id": snapshot_check.snapshot_id,
    }


# ---------- /api/reports/today ----------

def test_today_report_with_seeded_data(client, session):
    seeded = _seed_full_dataset(session)
    response = client.get("/api/reports/today")
    assert response.status_code == 200
    body = response.json()
    assert body["market_regime"]["regime"] == "UPTREND_EARLY"
    assert body["market_regime"]["risk_level"] == "MEDIUM"
    assert body["latest_run"]["run_id"] == seeded["run"].run_id
    assert body["latest_run"]["status"] == "SUCCESS"
    assert len(body["top_recommendations"]) == 1
    assert body["top_recommendations"][0]["symbol"] == "005930"
    assert body["top_recommendations"][0]["risk_summary"]["level"] == "LOW"
    assert len(body["holding_alerts"]) == 1
    assert body["holding_alerts"][0]["alert"] is True
    assert body["holding_alerts"][0]["risk_summary"]["level"] == "HIGH"
    assert "MA20_BREAKDOWN" in body["holding_alerts"][0]["risk_summary"]["flags"]


def test_today_report_empty_when_no_data(client):
    response = client.get("/api/reports/today")
    assert response.status_code == 200
    body = response.json()
    assert body["market_regime"] is None
    assert body["latest_run"] is None
    assert body["top_recommendations"] == []
    assert body["holding_alerts"] == []


# ---------- /api/recommendations/* ----------

def test_recommendations_latest_returns_run_with_recommendations(client, session):
    seeded = _seed_full_dataset(session)
    response = client.get("/api/recommendations/latest")
    assert response.status_code == 200
    body = response.json()
    assert body["run"]["run_id"] == seeded["run"].run_id
    assert body["run"]["telegram_sent"] is False
    assert len(body["recommendations"]) == 1
    rec = body["recommendations"][0]
    assert rec["rank"] == 1
    assert rec["symbol"] == "005930"
    assert rec["grade"] == "A"
    assert rec["total_score"] == "82.0000"
    assert rec["technical_score"] == "82.0000"
    assert rec["news_score"] == "50.0000"
    assert rec["supply_score"] == "55.0000"
    assert rec["fundamental_score"] == "50.0000"
    assert rec["ai_score"] == "55.0000"
    assert rec["risk_score"] == "0.0000"
    assert rec["risk_level"] == "LOW"
    assert rec["risk_flags"] == []
    assert rec["risk_summary"]["level"] == "LOW"
    assert rec["risk_summary"]["penalty"] == "0.0000"


def test_recommendations_latest_404_when_no_runs(client):
    response = client.get("/api/recommendations/latest")
    assert response.status_code == 404


def test_recommendations_history_returns_runs_with_counts(client, session):
    seeded = _seed_full_dataset(session)
    response = client.get("/api/recommendations/history?limit=10")
    assert response.status_code == 200
    body = response.json()
    assert body["limit"] == 10
    assert body["offset"] == 0
    assert len(body["items"]) == 1
    item = body["items"][0]
    assert item["run"]["run_id"] == seeded["run"].run_id
    assert item["recommendation_count"] == 1
    # Aggregates: 1 SUCCESS finalized at days_after=5 → 100% success rate
    assert item["success_rate"] == "100.0000"
    assert item["avg_close_return_1d"] == "1.5000"
    assert item["avg_close_return_3d"] == "2.5000"
    assert item["avg_close_return_5d"] == "3.0000"
    # 20-day result is PENDING with close_return=None → no eligible rows
    assert item["avg_close_return_20d"] is None


def test_recommendations_history_filters_by_date_range(client, session):
    seeded = _seed_full_dataset(session)
    response = client.get(
        "/api/recommendations/history?start_date=2026-05-05&end_date=2026-05-10",
    )
    assert response.status_code == 200
    assert response.json()["items"] == []


def test_recommendations_run_detail_404_for_unknown_id(client):
    response = client.get("/api/recommendations/9999")
    assert response.status_code == 404


def test_recommendations_run_detail_for_known_id(client, session):
    seeded = _seed_full_dataset(session)
    response = client.get(f"/api/recommendations/{seeded['run'].run_id}")
    assert response.status_code == 200
    body = response.json()
    assert body["run"]["run_id"] == seeded["run"].run_id
    assert body["run"]["telegram_sent"] is False
    rec = body["recommendations"][0]
    assert rec["risk_level"] == "LOW"
    assert rec["risk_flags"] == []
    assert rec["risk_summary"]["level"] == "LOW"
    assert rec["news_score"] == "50.0000"
    assert rec["supply_score"] == "55.0000"
    assert rec["fundamental_score"] == "50.0000"
    assert rec["ai_score"] == "55.0000"


def test_recommendations_run_detail_includes_result_rows(client, session):
    seeded = _seed_full_dataset(session)
    response = client.get(f"/api/recommendations/{seeded['run'].run_id}")
    body = response.json()
    rec = body["recommendations"][0]
    assert isinstance(rec["results"], list)
    by_days = {r["days_after"]: r for r in rec["results"]}
    assert set(by_days) == {1, 3, 5, 20}

    five = by_days[5]
    assert five["close_return"] == "3.0000"
    assert five["high_return"] == "4.0000"
    assert five["low_return"] == "-2.0000"
    assert five["max_drawdown"] == "-2.0000"
    assert five["result_status"] == "SUCCESS"
    assert five["result_date"] == "2026-05-09"

    pending = by_days[20]
    assert pending["result_status"] == "PENDING"
    assert pending["close_return"] is None
    assert pending["high_return"] is None


def test_recommendations_latest_includes_result_rows(client, session):
    _seed_full_dataset(session)
    response = client.get("/api/recommendations/latest")
    body = response.json()
    rec = body["recommendations"][0]
    days = {r["days_after"] for r in rec["results"]}
    assert days == {1, 3, 5, 20}


def test_today_report_top_recommendations_include_result_rows(client, session):
    _seed_full_dataset(session)
    response = client.get("/api/reports/today")
    body = response.json()
    top = body["top_recommendations"][0]
    days = {r["days_after"] for r in top["results"]}
    assert days == {1, 3, 5, 20}


def test_recommendations_run_detail_empty_results_list_when_none_seeded(
    client, session,
):
    """A recommendation without any RecommendationResult rows yields ``[]``."""
    run = RecommendationRunRepository(session).add(
        RecommendationRun(
            run_date=date(2026, 5, 4),
            started_at=datetime(2026, 5, 4, 6, 0, tzinfo=timezone.utc),
            status="SUCCESS",
            telegram_sent=False,
            market_summary={"phase": "test"},
        ),
    )
    session.flush()
    RecommendationRepository(session).add(
        Recommendation(
            run_id=run.run_id, rank=1, market="KOSPI",
            symbol="005930", name="삼성전자",
            grade="A", total_score=Decimal("80"),
        ),
    )
    session.commit()

    response = client.get(f"/api/recommendations/{run.run_id}")
    body = response.json()
    assert body["recommendations"][0]["results"] == []


def test_recommendations_history_aggregates_none_when_no_results(client, session):
    run = RecommendationRunRepository(session).add(
        RecommendationRun(
            run_date=date(2026, 5, 4),
            started_at=datetime(2026, 5, 4, 6, 0, tzinfo=timezone.utc),
            status="SUCCESS",
            telegram_sent=False,
            market_summary={"phase": "test"},
        ),
    )
    session.flush()
    RecommendationRepository(session).add(
        Recommendation(
            run_id=run.run_id, rank=1, market="KOSPI",
            symbol="005930", name="삼성전자",
            grade="A", total_score=Decimal("80"),
        ),
    )
    session.commit()

    response = client.get("/api/recommendations/history?limit=10")
    body = response.json()
    item = body["items"][0]
    assert item["recommendation_count"] == 1
    assert item["success_rate"] is None
    assert item["avg_close_return_1d"] is None
    assert item["avg_close_return_3d"] is None
    assert item["avg_close_return_5d"] is None
    assert item["avg_close_return_20d"] is None


def test_recommendations_history_success_rate_excludes_pending(client, session):
    """A FAILED + SUCCESS pair at days_after=5 yields 50% success rate.

    PENDING rows are excluded from both the numerator and denominator.
    """
    run = RecommendationRunRepository(session).add(
        RecommendationRun(
            run_date=date(2026, 5, 4),
            started_at=datetime(2026, 5, 4, 6, 0, tzinfo=timezone.utc),
            status="SUCCESS",
            telegram_sent=False,
            market_summary={"phase": "test"},
        ),
    )
    session.flush()
    rec_repo = RecommendationRepository(session)
    result_repo = RecommendationResultRepository(session)

    rec_a = rec_repo.add(
        Recommendation(run_id=run.run_id, rank=1, market="KOSPI",
                       symbol="A0001", name="A", grade="A",
                       total_score=Decimal("80")),
    )
    rec_b = rec_repo.add(
        Recommendation(run_id=run.run_id, rank=2, market="KOSPI",
                       symbol="B0001", name="B", grade="A",
                       total_score=Decimal("80")),
    )
    rec_c = rec_repo.add(
        Recommendation(run_id=run.run_id, rank=3, market="KOSPI",
                       symbol="C0001", name="C", grade="A",
                       total_score=Decimal("80")),
    )
    session.flush()
    for r, status, close in (
        (rec_a, "SUCCESS", Decimal("3.0")),
        (rec_b, "FAILED", Decimal("-6.0")),
        (rec_c, "PENDING", None),  # excluded from success_rate denominator
    ):
        result_repo.upsert(
            recommendation_id=r.id, days_after=5,
            result_date=date(2026, 5, 9),
            close_return=close,
            result_status=status,
        )
    session.commit()

    response = client.get("/api/recommendations/history?limit=10")
    item = response.json()["items"][0]
    assert item["success_rate"] == "50.0000"  # 1/2 finalized
    assert item["avg_close_return_5d"] == "-1.5000"  # mean(3.0, -6.0)


# ---------- /api/holdings* ----------

def test_holdings_lists_active_holdings(client, session):
    _seed_full_dataset(session)
    response = client.get("/api/holdings")
    assert response.status_code == 200
    body = response.json()
    assert len(body["items"]) == 1
    holding = body["items"][0]
    assert holding["symbol"] == "005930"
    assert holding["quantity"] == "10.0000"
    assert holding["avg_buy_price"] == "70000.0000"
    assert holding["is_active"] is True


def test_holdings_checks_latest(client, session):
    _seed_full_dataset(session)
    response = client.get("/api/holdings/checks/latest")
    assert response.status_code == 200
    body = response.json()
    assert len(body["items"]) == 1
    check = body["items"][0]
    assert check["symbol"] == "005930"
    assert check["alert"] is True
    assert check["decision"] == "SELL_REVIEW"
    assert check["risk_summary"]["level"] == "HIGH"
    assert "MA20_BREAKDOWN" in check["risk_summary"]["flags"]


def test_holdings_checks_latest_filters_by_check_type(client, session):
    _seed_full_dataset(session)
    response = client.get("/api/holdings/checks/latest?check_type=POST_MARKET")
    assert response.status_code == 200
    assert response.json()["items"] == []


def test_holdings_checks_latest_rejects_invalid_check_type(client):
    response = client.get("/api/holdings/checks/latest?check_type=MIDDAY")
    assert response.status_code == 422


def test_holdings_checks_for_symbol(client, session):
    _seed_full_dataset(session)
    response = client.get("/api/holdings/005930/checks")
    assert response.status_code == 200
    body = response.json()
    assert len(body["items"]) == 1
    assert body["items"][0]["symbol"] == "005930"


def test_holdings_checks_for_unknown_symbol_returns_empty(client):
    response = client.get("/api/holdings/UNKNOWN/checks")
    assert response.status_code == 200
    assert response.json()["items"] == []


# ---------- /api/stocks/{symbol} ----------

def test_stock_detail_returns_stock_with_latest_price_and_indicator(client, session):
    _seed_full_dataset(session)
    response = client.get("/api/stocks/005930")
    assert response.status_code == 200
    body = response.json()
    assert body["stock"]["symbol"] == "005930"
    assert body["stock"]["name"] == "삼성전자"
    assert body["latest_price"]["close"] == "70500.0000"
    assert body["latest_indicator"]["technical_score"] == "82.0000"
    assert body["latest_indicator"]["ma_alignment"] == "PERFECT_BULL"


def test_stock_detail_404_for_unknown_symbol(client):
    response = client.get("/api/stocks/UNKNOWN")
    assert response.status_code == 404


def test_stock_detail_returns_null_price_when_only_stock_seeded(client, session):
    _seed_stock(session, symbol="005930", name="삼성전자")
    session.commit()
    response = client.get("/api/stocks/005930")
    assert response.status_code == 200
    body = response.json()
    assert body["latest_price"] is None
    assert body["latest_indicator"] is None


# ---------- /api/universe/market-cap-top ----------

def test_universe_market_cap_top_uses_latest_date_when_unspecified(client, session):
    _seed_full_dataset(session)
    response = client.get("/api/universe/market-cap-top?market=KOSPI&limit=10")
    assert response.status_code == 200
    body = response.json()
    assert body["rank_date"] == "2026-05-04"
    assert body["market"] == "KOSPI"
    assert len(body["items"]) == 1
    assert body["items"][0]["rank"] == 1


def test_universe_market_cap_top_returns_empty_when_no_data(client):
    response = client.get("/api/universe/market-cap-top?market=KOSPI")
    assert response.status_code == 200
    body = response.json()
    assert body["items"] == []
    assert body["rank_date"] is None


# ---------- /api/market-regime/latest ----------

def test_market_regime_latest_returns_seeded_regime(client, session):
    _seed_full_dataset(session)
    response = client.get("/api/market-regime/latest")
    assert response.status_code == 200
    body = response.json()
    assert body["regime"] == "UPTREND_EARLY"
    assert body["risk_level"] == "MEDIUM"
    assert body["market_score"] == "72.0000"


def test_market_regime_latest_returns_null_when_empty(client):
    response = client.get("/api/market-regime/latest")
    assert response.status_code == 200
    assert response.json() is None


# ---------- /api/news ----------

def test_news_lists_seeded_news(client, session):
    _seed_full_dataset(session)
    response = client.get("/api/news")
    assert response.status_code == 200
    body = response.json()
    assert len(body["items"]) == 1
    assert body["items"][0]["title"] == "HBM 수요 강세"
    assert body["items"][0]["theme"] == "반도체"


def test_news_filters_by_symbol(client, session):
    _seed_full_dataset(session)
    response = client.get("/api/news?symbol=005930")
    assert response.status_code == 200
    assert len(response.json()["items"]) == 1

    response = client.get("/api/news?symbol=NOSUCH")
    assert response.json()["items"] == []


def test_news_filters_by_theme(client, session):
    _seed_full_dataset(session)
    assert client.get("/api/news?theme=반도체").json()["items"]
    assert client.get("/api/news?theme=AI").json()["items"] == []


# ---------- /api/jobs ----------

def test_jobs_lists_seeded_runs(client, session):
    _seed_full_dataset(session)
    response = client.get("/api/jobs")
    assert response.status_code == 200
    body = response.json()
    assert len(body["items"]) == 1
    assert body["items"][0]["job_name"] == "collect_close_data"
    assert body["items"][0]["status"] == "SUCCESS"
    assert body["items"][0]["result_summary"] == {"rows": 500}


def test_jobs_filters_by_status(client, session):
    _seed_full_dataset(session)
    assert client.get("/api/jobs?status=SUCCESS").json()["items"]
    assert client.get("/api/jobs?status=FAILED").json()["items"] == []


# ---------- /api/settings ----------

def test_settings_masks_sensitive_values(client):
    response = client.get("/api/settings")
    assert response.status_code == 200
    body = response.json()
    assert body["app_env"] == "test"
    assert body["telegram_enabled"] is False
    assert body["telegram_bot_token"] == "abcd****5678"
    assert body["telegram_chat_id"] == "12****12"
    assert body["kis_app_key"] == "kkkk****2222"
    assert body["kis_app_secret"] == "ssss****4444"
    assert body["kis_account_no"] == "9876****3210"
    # Plain literal token / chat_id never appear in response
    assert "abcd1234efgh5678" not in response.text
    assert "ssss3333ssss4444" not in response.text


def test_settings_feature_flags_off_by_default(client):
    response = client.get("/api/settings")
    body = response.json()
    assert body["feature_real_order_execution"] is False
    assert body["feature_full_auto"] is False
    assert body["feature_paper_trading"] is False
    assert body["feature_backtest"] is False
    assert body["feature_custom_ai_training"] is False


# ---------- existing health endpoint regression ----------

def test_health_endpoint_still_works(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
