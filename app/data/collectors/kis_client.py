import logging
from datetime import date, datetime, timedelta, timezone
from typing import Any

import httpx

from app.config.settings import Settings, get_settings
from app.data.interfaces import DataProviderInterface


logger = logging.getLogger(__name__)


class KisClientError(RuntimeError):
    """Base error for KIS client failures."""


class KisConfigurationError(KisClientError):
    """Raised when required KIS settings are missing."""


class KisApiError(KisClientError):
    """Raised when KIS returns an API-level or HTTP-level error."""


class KisTimeoutError(KisClientError):
    """Raised when a KIS request times out."""


class KisResponseFormatError(KisClientError):
    """Raised when a KIS response does not match the expected JSON shape."""


def mask_sensitive_value(value: str | None) -> str:
    if not value:
        return ""
    if len(value) <= 8:
        return "****"
    return f"{value[:4]}****{value[-4:]}"


def _mask_headers(headers: dict[str, str]) -> dict[str, str]:
    sensitive_names = {"authorization", "appkey", "appsecret", "personalseckey"}
    return {
        key: mask_sensitive_value(value) if key.lower() in sensitive_names else value
        for key, value in headers.items()
    }


class KisClient(DataProviderInterface):
    """Thin HTTP client for read-only KIS data APIs.

    This phase wires real request shapes and error handling. Tests must inject
    a mock httpx transport/client and must not call the real KIS service.
    """

    TOKEN_PATH = "/oauth2/tokenP"
    CURRENT_PRICE_PATH = "/uapi/domestic-stock/v1/quotations/inquire-price"
    DAILY_PRICE_PATH = "/uapi/domestic-stock/v1/quotations/inquire-daily-itemchartprice"
    MARKET_CAP_RANKING_PATH = "/uapi/domestic-stock/v1/ranking/market-cap"

    TR_ID_CURRENT_PRICE = "FHKST01010100"
    TR_ID_DAILY_PRICE = "FHKST03010100"
    TR_ID_MARKET_CAP_RANKING = "FHPST01740000"

    # KIS 시총 상위 화면(screen) 카테고리 코드. KIS 모의투자 서버는 이
    # 파라미터를 강제하므로 누락 시 OPSQ2001 ERROR INPUT FIELD NOT FOUND
    # 응답이 돌아온다.
    MARKET_CAP_SCREEN_DIV_CODE = "20174"

    def __init__(
        self,
        settings: Settings | None = None,
        http_client: httpx.Client | None = None,
        access_token: str | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self._owns_http_client = http_client is None
        self._http = http_client or httpx.Client(
            base_url=self.settings.effective_kis_base_url,
            timeout=self.settings.kis_timeout_seconds,
        )
        self._access_token = access_token
        self._access_token_expires_at: datetime | None = None

    def close(self) -> None:
        if self._owns_http_client:
            self._http.close()

    def __enter__(self) -> "KisClient":
        return self

    def __exit__(self, *_exc_info: object) -> None:
        self.close()

    def issue_access_token(self, force: bool = False) -> str:
        """Issue or reuse an access token using KIS client credentials."""
        if not force and self._access_token and not self._is_access_token_expired():
            return self._access_token

        self._require_credentials()
        payload = {
            "grant_type": "client_credentials",
            "appkey": self.settings.kis_app_key,
            "appsecret": self.settings.kis_app_secret,
        }
        data = self._request(
            "POST",
            self.TOKEN_PATH,
            json_body=payload,
            require_auth=False,
            validate_api_code=False,
        )

        token = data.get("access_token")
        if not isinstance(token, str) or not token:
            raise KisResponseFormatError("KIS token response is missing access_token.")

        expires_in = data.get("expires_in", 0)
        try:
            expires_delta = timedelta(seconds=max(int(expires_in) - 60, 0))
        except (TypeError, ValueError):
            expires_delta = timedelta()

        self._access_token = token
        self._access_token_expires_at = datetime.now(timezone.utc) + expires_delta
        return token

    def refresh_access_token(self) -> str:
        """Force token reissue. KIS client-credentials auth has no refresh endpoint here."""
        return self.issue_access_token(force=True)

    def fetch_current_price(self, symbol: str) -> dict[str, Any]:
        data = self._request(
            "GET",
            self.CURRENT_PRICE_PATH,
            params={
                "FID_COND_MRKT_DIV_CODE": "J",
                "FID_INPUT_ISCD": symbol,
            },
            headers={"tr_id": self.TR_ID_CURRENT_PRICE},
        )
        output = data.get("output")
        if not isinstance(output, dict):
            raise KisResponseFormatError("KIS current price response is missing output object.")
        return data

    def fetch_daily_prices(
        self,
        symbol: str,
        start_date: date,
        end_date: date,
    ) -> list[dict[str, Any]]:
        data = self._request(
            "GET",
            self.DAILY_PRICE_PATH,
            params={
                "FID_COND_MRKT_DIV_CODE": "J",
                "FID_INPUT_ISCD": symbol,
                "FID_INPUT_DATE_1": start_date.strftime("%Y%m%d"),
                "FID_INPUT_DATE_2": end_date.strftime("%Y%m%d"),
                "FID_PERIOD_DIV_CODE": "D",
                "FID_ORG_ADJ_PRC": "0",
            },
            headers={"tr_id": self.TR_ID_DAILY_PRICE},
        )
        rows = data.get("output2")
        if not isinstance(rows, list):
            raise KisResponseFormatError("KIS daily price response is missing output2 list.")
        return rows

    def fetch_market_cap_rankings(
        self,
        market: str,
        ranking_date: date,
        limit: int,
    ) -> list[dict[str, Any]]:
        data = self._request(
            "GET",
            self.MARKET_CAP_RANKING_PATH,
            params={
                "FID_COND_MRKT_DIV_CODE": self._market_division_code(market),
                "FID_COND_SCR_DIV_CODE": self.MARKET_CAP_SCREEN_DIV_CODE,
                "FID_INPUT_ISCD": "0000",
                "FID_DIV_CLS_CODE": "0",
                "FID_BLNG_CLS_CODE": "0",
                "FID_TRGT_CLS_CODE": "0",
                "FID_TRGT_EXLS_CLS_CODE": "0",
                "FID_INPUT_PRICE_1": "",
                "FID_INPUT_PRICE_2": "",
                "FID_VOL_CNT": "",
            },
            headers={"tr_id": self.TR_ID_MARKET_CAP_RANKING},
        )
        rows = data.get("output")
        if not isinstance(rows, list):
            raise KisResponseFormatError("KIS market cap response is missing output list.")
        return rows[:limit]

    def fetch_news(self, query, start_time, end_time):  # type: ignore[no-untyped-def]
        raise NotImplementedError("News collection is outside Phase 3-2.")

    def fetch_disclosures(self, symbols, target_date):  # type: ignore[no-untyped-def]
        raise NotImplementedError("Disclosure collection is outside Phase 3-2.")

    def _request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        json_body: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
        require_auth: bool = True,
        validate_api_code: bool = True,
    ) -> dict[str, Any]:
        request_headers = self._base_headers(require_auth=require_auth)
        if headers:
            request_headers.update(headers)

        logger.debug(
            "KIS HTTP %s %s headers=%s params=%s",
            method,
            path,
            _mask_headers(request_headers),
            params or {},
        )

        try:
            response = self._http.request(
                method,
                path,
                params=params,
                json=json_body,
                headers=request_headers,
            )
        except httpx.TimeoutException as exc:
            raise KisTimeoutError(f"KIS request timed out: {method} {path}") from exc
        except httpx.HTTPError as exc:
            raise KisClientError(f"KIS request failed: {method} {path}") from exc

        if response.status_code >= 400:
            raise KisApiError(f"KIS HTTP error {response.status_code}: {method} {path}")

        try:
            data = response.json()
        except ValueError as exc:
            raise KisResponseFormatError("KIS response is not valid JSON.") from exc

        if not isinstance(data, dict):
            raise KisResponseFormatError("KIS response JSON must be an object.")

        if validate_api_code and data.get("rt_cd") not in (None, "0"):
            msg_cd = data.get("msg_cd", "UNKNOWN")
            msg = data.get("msg1") or data.get("msg")
            raise KisApiError(f"KIS API error {msg_cd}: {msg or 'no message'}")

        return data

    def _base_headers(self, *, require_auth: bool) -> dict[str, str]:
        self._require_credentials()
        headers = {
            "content-type": "application/json; charset=utf-8",
            "appkey": self.settings.kis_app_key,
            "appsecret": self.settings.kis_app_secret,
        }
        if require_auth:
            token = self.issue_access_token()
            headers["authorization"] = f"Bearer {token}"
        return headers

    def _require_credentials(self) -> None:
        if not self.settings.kis_app_key or not self.settings.kis_app_secret:
            raise KisConfigurationError("KIS_APP_KEY and KIS_APP_SECRET are required.")

    def _is_access_token_expired(self) -> bool:
        if self._access_token_expires_at is None:
            return False
        return datetime.now(timezone.utc) >= self._access_token_expires_at

    @staticmethod
    def _market_division_code(market: str) -> str:
        normalized = market.strip().upper()
        if normalized in {"KOSPI", "J"}:
            return "J"
        if normalized in {"KOSDAQ", "Q"}:
            return "Q"
        return normalized or "J"
