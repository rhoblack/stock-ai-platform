def test_settings_defaults():
    from app.config.settings import get_settings

    settings = get_settings()

    assert settings.app_name == "stock_ai_platform"
    assert settings.feature_real_order_execution is False
    assert settings.feature_full_auto is False


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
