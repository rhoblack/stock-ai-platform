from datetime import date

import httpx
import pytest

from app.config.settings import Settings
from app.data.collectors.kis_client import (
    KisApiError,
    KisClient,
    KisResponseFormatError,
    KisTimeoutError,
)
from tests.mocks.kis_responses import (
    CURRENT_PRICE_RESPONSE,
    DAILY_PRICE_RESPONSE,
    MARKET_CAP_RANKING_RESPONSE,
)


def _settings() -> Settings:
    return Settings(
        kis_app_key="fake_app_key_for_tests",
        kis_app_secret="fake_app_secret_for_tests",
        kis_use_paper=True,
        kis_paper_base_url="https://mock-kis.local",
    )


def _client(handler, *, access_token: str = "mock_access_token") -> KisClient:
    http_client = httpx.Client(
        transport=httpx.MockTransport(handler),
        base_url="https://mock-kis.local",
    )
    return KisClient(settings=_settings(), http_client=http_client, access_token=access_token)


def test_issue_access_token_uses_mock_http_response():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["path"] = request.url.path
        seen["body"] = request.content.decode()
        return httpx.Response(
            200,
            json={
                "access_token": "mock_access_token_from_kis",
                "token_type": "Bearer",
                "expires_in": 3600,
            },
        )

    client = _client(handler, access_token="")

    token = client.issue_access_token()

    assert token == "mock_access_token_from_kis"
    assert seen["path"] == "/oauth2/tokenP"
    assert "fake_app_key_for_tests" in seen["body"]
    assert "fake_app_secret_for_tests" in seen["body"]


def test_fetch_current_price_uses_mock_http_response():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["path"] = request.url.path
        seen["symbol"] = request.url.params["FID_INPUT_ISCD"]
        seen["tr_id"] = request.headers["tr_id"]
        return httpx.Response(200, json=CURRENT_PRICE_RESPONSE)

    client = _client(handler)

    result = client.fetch_current_price("005930")

    assert result == CURRENT_PRICE_RESPONSE
    assert seen == {
        "path": "/uapi/domestic-stock/v1/quotations/inquire-price",
        "symbol": "005930",
        "tr_id": "FHKST01010100",
    }


def test_fetch_daily_prices_uses_mock_http_response():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["path"] = request.url.path
        seen["date_1"] = request.url.params["FID_INPUT_DATE_1"]
        seen["date_2"] = request.url.params["FID_INPUT_DATE_2"]
        return httpx.Response(200, json=DAILY_PRICE_RESPONSE)

    client = _client(handler)

    result = client.fetch_daily_prices("005930", date(2026, 5, 1), date(2026, 5, 4))

    assert result == DAILY_PRICE_RESPONSE["output2"]
    assert seen == {
        "path": "/uapi/domestic-stock/v1/quotations/inquire-daily-itemchartprice",
        "date_1": "20260501",
        "date_2": "20260504",
    }


def test_fetch_market_cap_rankings_uses_mock_http_response_and_limit():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["path"] = request.url.path
        seen["market"] = request.url.params["FID_COND_MRKT_DIV_CODE"]
        seen["screen_div"] = request.url.params["FID_COND_SCR_DIV_CODE"]
        seen["tr_id"] = request.headers["tr_id"]
        return httpx.Response(200, json=MARKET_CAP_RANKING_RESPONSE)

    client = _client(handler)

    result = client.fetch_market_cap_rankings("KOSPI", date(2026, 5, 4), limit=1)

    assert result == MARKET_CAP_RANKING_RESPONSE["output"][:1]
    # FID_COND_SCR_DIV_CODE="20174" 가 누락되면 KIS paper 서버는 OPSQ2001
    # ERROR INPUT FIELD NOT FOUND 로 거절한다 (실 KIS 서버 검증 결과).
    assert seen == {
        "path": "/uapi/domestic-stock/v1/ranking/market-cap",
        "market": "J",
        "screen_div": "20174",
        "tr_id": "FHPST01740000",
    }


def test_request_helper_raises_api_error_on_kis_failure_code():
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={"rt_cd": "1", "msg_cd": "KIS0001", "msg1": "mock failure"},
        )

    client = _client(handler)

    with pytest.raises(KisApiError, match="KIS0001"):
        client.fetch_current_price("005930")


def test_request_helper_raises_timeout_error():
    def handler(_request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("mock timeout")

    client = _client(handler)

    with pytest.raises(KisTimeoutError):
        client.fetch_current_price("005930")


def test_request_helper_raises_format_error_for_invalid_json():
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=b"not-json")

    client = _client(handler)

    with pytest.raises(KisResponseFormatError):
        client.fetch_current_price("005930")


def test_fetch_current_price_rejects_unexpected_response_shape():
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"rt_cd": "0", "msg_cd": "MCA00000"})

    client = _client(handler)

    with pytest.raises(KisResponseFormatError, match="output"):
        client.fetch_current_price("005930")


def test_kis_client_logs_mask_sensitive_headers(caplog):
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=CURRENT_PRICE_RESPONSE)

    client = _client(handler, access_token="mock_sensitive_access_token")

    with caplog.at_level("DEBUG", logger="app.data.collectors.kis_client"):
        client.fetch_current_price("005930")

    assert "fake_app_key_for_tests" not in caplog.text
    assert "fake_app_secret_for_tests" not in caplog.text
    assert "mock_sensitive_access_token" not in caplog.text
    assert "****" in caplog.text
