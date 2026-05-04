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
    from fastapi.testclient import TestClient

    from app.main import app

    client = TestClient(app)
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "app": "stock_ai_platform",
        "env": "local",
    }
