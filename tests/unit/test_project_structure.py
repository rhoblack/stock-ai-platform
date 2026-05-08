def test_settings_defaults():
    from app.config.settings import get_settings

    settings = get_settings()

    assert settings.app_name == "stock_ai_platform"
    assert settings.feature_real_order_execution is False
    assert settings.feature_full_auto is False
    assert settings.collect_market == "KOSPI"
    assert settings.market_cap_limit == 500
    assert settings.market_cap_universe_name == "MARKET_CAP_TOP_500"
    assert settings.daily_price_lookback_days == 1
    assert settings.daily_price_batch_size == 100
    assert settings.indicator_universe_name == "MARKET_CAP_TOP_500"
    assert settings.indicator_lookback_days == 250
    assert settings.indicator_batch_size == 100
    # v0.5 Phase A PR2 — 뉴스 자동 수집은 default OFF. 운영자가 .env 에
    # NEWS_COLLECTION_ENABLED=true 를 명시 설정한 경우에만 enable.
    assert settings.news_collection_enabled is False
    # v0.5 Phase B — 공시 자동 수집도 default OFF. DISCLOSURE_COLLECTION_ENABLED=true
    # 명시 설정 시에만 enable.
    assert settings.disclosure_collection_enabled is False
    # v0.14 Phase B — Paper / Simulation Trading 마스터 스위치도 default OFF.
    # PAPER_TRADING_ENABLED=true 명시 설정 시에만 SimulationBroker.submit_order
    # 가 VirtualOrder 행을 기록한다 (외부 호출 0건 정책 그대로 유지).
    assert settings.paper_trading_enabled is False


def test_interfaces_importable():
    from app.ai.interfaces import AIProviderInterface
    from app.broker.interfaces import BrokerInterface
    from app.data.interfaces import DataProviderInterface
    from app.decision.interfaces import StrategyInterface

    assert AIProviderInterface is not None
    assert BrokerInterface is not None
    assert DataProviderInterface is not None
    assert StrategyInterface is not None


def test_fastapi_app_metadata():
    from app.main import app

    assert app.title == "stock_ai_platform"
    assert app.version == "0.1.0"


def test_health_check_endpoint():
    """/health 응답이 현재 Settings.app_env 를 그대로 반영하는지 검증.

    `app_env` 는 APP_ENV 환경 변수로 주입되므로 로컬 (`local`) 과 CI (`ci`)
    에서 값이 달라진다. 테스트는 하드코딩 대신 ``get_settings().app_env`` 를
    참조해 환경 무관하게 통과하도록 한다 (`/health` 의 계약은 "현재 설정의
    `app_env` 를 그대로 노출한다" 이며, 그 계약을 그대로 단언한다).
    """
    from fastapi.testclient import TestClient

    from app.config.settings import get_settings
    from app.main import app

    client = TestClient(app)
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "app": "stock_ai_platform",
        "env": get_settings().app_env,
    }
