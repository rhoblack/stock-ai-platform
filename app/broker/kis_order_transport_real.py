"""KIS Order Transport — real httpx implementation (v1.0 Phase B).

This module introduces ``HttpxKisOrderTransport`` — the FIRST concrete
implementation of :class:`KisOrderClientInterface` that issues actual HTTP
requests via ``httpx``. It is **never wired into** ``RealOrderExecutor``
real-path execution by Phase B; that wiring belongs to Phase C and stays
guarded by the paranoid ``REAL_ORDER_DRY_RUN`` / ``KIS_ORDER_ENABLED`` /
``REAL_TRADING_ENABLED`` triple-gate. The transport itself is fully
unit-tested with ``respx``-mocked HTTP responses — production code paths
in this module never reach the real KIS API during the test suite.

Hard guarantees verified by the test suite
------------------------------------------
* ``httpx`` is imported lazily inside ``__init__`` only — module-level
  import remains free of ``httpx`` so the v0.10 / v0.11 no-network
  monkeypatch guards stay effective.
* No ``requests`` / ``urllib`` import.
* No ``app.providers.kis`` / ``app.data.collectors.kis_client`` import —
  this transport is structurally separate from the read-only data layer.
* Sensitive credentials (``app_key`` / ``app_secret`` / ``access_token`` /
  ``account_no``) NEVER appear in ``__repr__``, ``str()``, log messages,
  or response objects.
* No raw KIS response is ever stored or returned — only whitelisted
  fields are decoded and re-projected into the immutable
  ``KisOrderResult`` / ``KisFillStatusResult`` / ``KisCancelResult``
  dataclasses (defined in :mod:`app.broker.kis_order_client`).
* ``broker_order_no`` is exposed as plaintext ONLY through the dataclass
  ``order_no`` field returned to upstream callers (the executor in
  Phase C). The upstream layer is responsible for SHA-256 hashing it
  before persistence (see ``RealOrder.broker_order_no_hash`` schema in
  v0.16 Phase C). This module never persists or logs the plaintext
  order number.

Retry policy
------------
* ``place_order`` — **retry=0**. Re-issuing a place order against KIS
  introduces a duplicate-fill risk because the prior request may have
  arrived and been processed even when we never received the response.
  Operators handle the response-loss case manually via
  ``RUNBOOK_REAL_TRADING.md`` § 5.
* ``query_fill_status`` — **retry up to 2** on transient transport-layer
  failure (TimeoutException / NetworkError). HTTP 4xx/5xx responses are
  NOT retried — the server reached us and gave a definitive answer.
* ``cancel_order`` — **retry up to 2**. Cancellation is idempotent on
  the KIS side (the service rejects a second cancel of an already-
  canceled order with a known business code).

Response classification
-----------------------
``place_order`` outcomes (mapped to :class:`KisOrderResult`):

  ============= ============================ ==================================
  internal      KisOrderResult.success        message prefix (and dataclass map)
  ============= ============================ ==================================
  SUBMITTED     True                          "SUBMITTED: ..."
  REJECTED      False                         "REJECTED: ..."
  TIMEOUT       False                         "TIMEOUT: ..."
  NETWORK_ERROR False                         "NETWORK_ERROR: ..."
  UNKNOWN       False                         "UNKNOWN: ..."
  ============= ============================ ==================================

``query_fill_status`` outcomes (mapped to :class:`KisFillStatusResult`):

  ============= ================================== ==========
  internal      KisFillStatusResult.status         success
  ============= ================================== ==========
  FULL          "FILLED"                           True
  PARTIAL       "PARTIALLY_FILLED"                 True
  NONE          "PENDING"                          True
  REJECTED      "REJECTED"                         False
  CANCELED      "CANCELED"                         False
  UNKNOWN       "PENDING"                          False
  ============= ================================== ==========

  (``KisFillStatusResult.VALID_STATUSES`` constrains the dataclass to
  the 5 KIS-canonical statuses; ``UNKNOWN`` surfaces as ``success=False``
  with ``message`` carrying the diagnostic.)

``cancel_order`` outcomes (mapped to :class:`KisCancelResult`):

  ============= ====================
  internal      KisCancelResult.success
  ============= ====================
  CANCELED      True
  REJECTED      False
  TIMEOUT       False
  NETWORK_ERROR False
  UNKNOWN       False
  ============= ====================

The internal classification is exposed as the result ``message``
prefix (uppercase token before ``": "``) so upstream callers in Phase C
can branch on the categorical outcome without re-parsing details.
"""

from __future__ import annotations

import logging
from typing import Any, Callable, TypeVar

from app.broker.kis_order_client import (
    KisCancelResult,
    KisFillStatusResult,
    KisOrderClientInterface,
    KisOrderRequest,
    KisOrderResult,
    mask_sensitive_order_payload,
)
from app.config.logging import install_sensitive_qs_filter
from app.config.settings import Settings, get_settings


logger = logging.getLogger(__name__)


T = TypeVar("T")


# ---------------------------------------------------------------------------
# Endpoints + KIS TR_IDs (used as constants — paths are exercised only by
# respx mock during the test suite; real KIS calls never occur in CI).
# ---------------------------------------------------------------------------

_PLACE_ORDER_PATH = "/uapi/domestic-stock/v1/trading/order-cash"
_QUERY_FILL_PATH = "/uapi/domestic-stock/v1/trading/inquire-ccnl"
_CANCEL_ORDER_PATH = "/uapi/domestic-stock/v1/trading/order-rvsecncl"

# KIS TR_ID constants (paper-trading variants are used by default;
# operators flip to live TR_IDs only after the runbook §2 activation).
_TR_ID_BUY = "VTTC0802U"
_TR_ID_SELL = "VTTC0801U"
_TR_ID_QUERY = "VTTC8001R"
_TR_ID_CANCEL = "VTTC0803U"

# Retry caps (per RUNBOOK § 5 / PLAN-0017 Phase B)
_PLACE_ORDER_MAX_RETRIES = 0  # NEVER retry place — duplicate-order risk
_QUERY_FILL_MAX_RETRIES = 2
_CANCEL_ORDER_MAX_RETRIES = 2


# ---------------------------------------------------------------------------
# Internal classification tokens
# ---------------------------------------------------------------------------


class PlaceClassification:
    SUBMITTED = "SUBMITTED"
    REJECTED = "REJECTED"
    TIMEOUT = "TIMEOUT"
    NETWORK_ERROR = "NETWORK_ERROR"
    UNKNOWN = "UNKNOWN"


class FillClassification:
    FULL = "FULL"
    PARTIAL = "PARTIAL"
    NONE = "NONE"
    REJECTED = "REJECTED"
    CANCELED = "CANCELED"
    UNKNOWN = "UNKNOWN"


class CancelClassification:
    CANCELED = "CANCELED"
    REJECTED = "REJECTED"
    TIMEOUT = "TIMEOUT"
    NETWORK_ERROR = "NETWORK_ERROR"
    UNKNOWN = "UNKNOWN"


# Mapping from internal FillClassification to KisFillStatusResult.status
# (the dataclass restricts status to 5 canonical KIS strings).
_FILL_STATUS_MAP: dict[str, str] = {
    FillClassification.FULL: "FILLED",
    FillClassification.PARTIAL: "PARTIALLY_FILLED",
    FillClassification.NONE: "PENDING",
    FillClassification.REJECTED: "REJECTED",
    FillClassification.CANCELED: "CANCELED",
    FillClassification.UNKNOWN: "PENDING",
}

# success=True only for the three "definite" non-error fill states.
_FILL_SUCCESS_MAP: dict[str, bool] = {
    FillClassification.FULL: True,
    FillClassification.PARTIAL: True,
    FillClassification.NONE: True,
    FillClassification.REJECTED: False,
    FillClassification.CANCELED: False,
    FillClassification.UNKNOWN: False,
}


# ---------------------------------------------------------------------------
# Retry helper (pure, fully testable — no httpx dependency)
# ---------------------------------------------------------------------------


class _RetryAttempt:
    """Internal sentinel — operation function returns one of these.

    ``retry`` indicates the operation should be retried (TIMEOUT /
    NETWORK_ERROR). ``final`` indicates a definitive outcome that must
    be returned to the caller without retry (HTTP 200 / 4xx / 5xx).
    """

    __slots__ = ("classification", "result", "should_retry")

    def __init__(
        self,
        *,
        classification: str,
        result: object,
        should_retry: bool,
    ) -> None:
        self.classification = classification
        self.result = result
        self.should_retry = should_retry


def _run_with_retries(
    operation: Callable[[], _RetryAttempt],
    *,
    max_retries: int,
) -> _RetryAttempt:
    """Call ``operation`` up to (1 + max_retries) times.

    Returns immediately when ``operation()`` yields a non-retry attempt
    (HTTP-layer success or definitive HTTP-layer rejection). Returns the
    LAST attempt after exhausting retries on transient failure.

    Pure, side-effect free, no httpx import — tests inject a function
    that returns canned ``_RetryAttempt`` objects to exercise the
    retry loop deterministically.
    """
    last = operation()
    attempts_used = 1
    while last.should_retry and attempts_used <= max_retries:
        last = operation()
        attempts_used += 1
    return last


# ---------------------------------------------------------------------------
# Account / payload masking helpers
# ---------------------------------------------------------------------------


def _mask_account(account_no: str) -> str:
    if len(account_no) >= 4:
        return "****" + account_no[-4:]
    return "****"


# ---------------------------------------------------------------------------
# Real httpx transport
# ---------------------------------------------------------------------------


class HttpxKisOrderTransport(KisOrderClientInterface):
    """Real httpx-backed transport for KIS order placement / query / cancel.

    Construction
    ------------
    ``settings`` defaults to :func:`get_settings`. ``client`` may be a
    pre-built ``httpx.Client`` injected by tests (the ``respx`` test
    pattern); when ``None``, the constructor lazily imports ``httpx``
    and builds a default client bound to ``settings.kis_order_base_url``.

    Tests inject ``client=respx_mocked_client`` so the transport never
    issues outbound traffic. Production callers (Phase C onwards) pass
    ``client=None`` and rely on the lazy default.

    Credentials
    -----------
    ``app_key`` / ``app_secret`` / ``access_token`` / ``account_no`` may
    be passed explicitly; otherwise they fall back to the existing
    ``KIS_APP_KEY`` / ``KIS_APP_SECRET`` / ``KIS_ACCOUNT_NO`` settings
    (the access token does NOT have a default — Phase C wires the token
    refresh manager). Credentials are stored on private attributes,
    never appear in ``__repr__``, ``as_dict()``, or any log message.
    """

    __slots__ = (
        "_settings",
        "_client",
        "_httpx",
        "_app_key",
        "_app_secret",
        "_access_token",
        "_account_no",
        "_user_agent",
    )

    def __init__(
        self,
        *,
        settings: Settings | None = None,
        client: Any | None = None,
        app_key: str | None = None,
        app_secret: str | None = None,
        access_token: str | None = None,
        account_no: str | None = None,
        user_agent: str = "stock-ai-platform/1.0 KIS order transport",
    ) -> None:
        s = settings or get_settings()
        self._settings = s

        # Lazy httpx import — module-level import stays clean so the
        # v0.10 / v0.11 no-network monkeypatch guards remain effective
        # for any test that imports this module without constructing
        # an instance.
        import httpx  # noqa: PLC0415

        # Install secret-masking filter on httpx's request logger BEFORE
        # building the client so the very first request line is masked.
        # Idempotent — only takes effect once per process.
        install_sensitive_qs_filter("httpx")

        if client is None:
            client = httpx.Client(
                base_url=s.kis_order_base_url,
                headers={"User-Agent": user_agent},
                follow_redirects=False,
            )
        self._client = client
        self._httpx = httpx

        self._app_key = app_key if app_key is not None else s.kis_app_key
        self._app_secret = (
            app_secret if app_secret is not None else s.kis_app_secret
        )
        self._access_token = access_token if access_token is not None else ""
        self._account_no = (
            account_no if account_no is not None else s.kis_account_no
        )
        self._user_agent = user_agent

    # ----- repr / introspection (must NOT leak credentials) -------------

    def __repr__(self) -> str:
        return (
            f"HttpxKisOrderTransport(base_url={self._settings.kis_order_base_url!r}, "
            f"account_no={_mask_account(self._account_no)!r})"
        )

    def __str__(self) -> str:
        return self.__repr__()

    def as_dict(self) -> dict[str, Any]:
        """JSON-safe descriptor — credentials never appear."""
        return {
            "base_url": self._settings.kis_order_base_url,
            "account_no_masked": _mask_account(self._account_no),
            "user_agent": self._user_agent,
        }

    # ----- header construction (used by all 3 methods) ------------------

    def _headers(self, *, tr_id: str) -> dict[str, str]:
        """Build outbound HTTP headers. Caller MUST never log this dict
        without going through :func:`mask_sensitive_order_payload`."""
        return {
            "content-type": "application/json; charset=utf-8",
            "authorization": f"Bearer {self._access_token}",
            "appkey": self._app_key,
            "appsecret": self._app_secret,
            "tr_id": tr_id,
        }

    def _account_split(self) -> tuple[str, str]:
        """Split internal account_no into KIS CANO (8 chars) + ACNT_PRDT_CD (2 chars)."""
        acct = self._account_no or ""
        if len(acct) >= 10:
            return acct[:8], acct[8:10]
        if len(acct) >= 8:
            return acct[:8], "01"
        return acct, "01"

    # ----- place_order --------------------------------------------------

    def place_order(self, request: KisOrderRequest) -> KisOrderResult:
        tr_id = _TR_ID_BUY if request.side == "BUY" else _TR_ID_SELL
        cano, acnt_prdt_cd = self._account_split()
        body: dict[str, Any] = {
            "CANO": cano,
            "ACNT_PRDT_CD": acnt_prdt_cd,
            "PDNO": request.symbol,
            "ORD_DVSN": "01" if request.order_type == "MARKET" else "00",
            "ORD_QTY": str(request.quantity),
            "ORD_UNPR": (
                str(request.price) if request.order_type == "LIMIT" else "0"
            ),
        }
        # Logging the body is safe ONLY through the masker — body itself
        # never contains app_key/app_secret, but defense in depth.
        logger.debug(
            "kis_place_order issuing tr_id=%s payload=%s",
            tr_id,
            mask_sensitive_order_payload(body),
        )

        def attempt() -> _RetryAttempt:
            try:
                response = self._client.post(
                    _PLACE_ORDER_PATH,
                    headers=self._headers(tr_id=tr_id),
                    json=body,
                    timeout=self._settings.kis_order_place_timeout_s,
                )
            except self._httpx.TimeoutException as exc:
                return _RetryAttempt(
                    classification=PlaceClassification.TIMEOUT,
                    result=KisOrderResult(
                        success=False,
                        order_no="",
                        message=f"TIMEOUT: KIS place_order exceeded "
                        f"{self._settings.kis_order_place_timeout_s}s",
                    ),
                    should_retry=True,
                )
            except self._httpx.HTTPError as exc:
                return _RetryAttempt(
                    classification=PlaceClassification.NETWORK_ERROR,
                    result=KisOrderResult(
                        success=False,
                        order_no="",
                        message=f"NETWORK_ERROR: {type(exc).__name__}",
                    ),
                    should_retry=True,
                )
            return _RetryAttempt(
                classification="",  # filled below
                result=self._classify_place_response(response),
                should_retry=False,
            )

        outcome = _run_with_retries(
            attempt, max_retries=_PLACE_ORDER_MAX_RETRIES
        )
        return outcome.result  # type: ignore[return-value]

    def _classify_place_response(self, response: Any) -> KisOrderResult:
        """Map an HTTP response (200/4xx/5xx) to a KisOrderResult.

        Whitelisted body fields: ``output.KRX_FWDG_ORD_ORGNO`` /
        ``output.ODNO`` (order number), ``rt_cd`` (business code, 0 = ok),
        ``msg_cd`` / ``msg1`` (short human label).
        Raw response is NEVER stored or returned.
        """
        status_code = response.status_code

        if status_code >= 500:
            return KisOrderResult(
                success=False,
                order_no="",
                message=f"UNKNOWN: KIS HTTP {status_code} (server error)",
            )
        if status_code >= 400:
            return KisOrderResult(
                success=False,
                order_no="",
                message=f"REJECTED: KIS HTTP {status_code}",
            )
        if status_code != 200:
            return KisOrderResult(
                success=False,
                order_no="",
                message=f"UNKNOWN: KIS HTTP {status_code}",
            )

        try:
            payload = response.json()
        except (ValueError, Exception) as exc:  # noqa: BLE001
            return KisOrderResult(
                success=False,
                order_no="",
                message=f"UNKNOWN: KIS HTTP 200 but body is not valid JSON",
            )

        if not isinstance(payload, dict):
            return KisOrderResult(
                success=False,
                order_no="",
                message="UNKNOWN: KIS HTTP 200 but body is not a JSON object",
            )

        rt_cd = str(payload.get("rt_cd") or "")
        msg1 = str(payload.get("msg1") or "")[:120]
        output = payload.get("output")
        if rt_cd == "0":
            order_no = ""
            if isinstance(output, dict):
                order_no = str(output.get("ODNO") or "")
            return KisOrderResult(
                success=True,
                order_no=order_no,
                message=f"SUBMITTED: {msg1}" if msg1 else "SUBMITTED",
            )
        # KIS business-error code (rt_cd != "0").
        return KisOrderResult(
            success=False,
            order_no="",
            message=f"REJECTED: rt_cd={rt_cd or '?'} {msg1}".strip(),
        )

    # ----- query_fill_status -------------------------------------------

    def query_fill_status(self, order_no: str) -> KisFillStatusResult:
        cano, acnt_prdt_cd = self._account_split()
        params: dict[str, Any] = {
            "CANO": cano,
            "ACNT_PRDT_CD": acnt_prdt_cd,
            "ODNO": order_no,
        }
        logger.debug(
            "kis_query_fill_status order_no=%s",
            order_no,
        )

        def attempt() -> _RetryAttempt:
            try:
                response = self._client.get(
                    _QUERY_FILL_PATH,
                    headers=self._headers(tr_id=_TR_ID_QUERY),
                    params=params,
                    timeout=self._settings.kis_order_query_timeout_s,
                )
            except self._httpx.TimeoutException as exc:
                return _RetryAttempt(
                    classification=FillClassification.UNKNOWN,
                    result=KisFillStatusResult(
                        success=False,
                        order_no=order_no,
                        filled_quantity=0,
                        remaining_quantity=0,
                        status="PENDING",
                        message=f"UNKNOWN: TIMEOUT after "
                        f"{self._settings.kis_order_query_timeout_s}s",
                    ),
                    should_retry=True,
                )
            except self._httpx.HTTPError as exc:
                return _RetryAttempt(
                    classification=FillClassification.UNKNOWN,
                    result=KisFillStatusResult(
                        success=False,
                        order_no=order_no,
                        filled_quantity=0,
                        remaining_quantity=0,
                        status="PENDING",
                        message=f"UNKNOWN: NETWORK_ERROR: {type(exc).__name__}",
                    ),
                    should_retry=True,
                )
            return _RetryAttempt(
                classification="",
                result=self._classify_fill_response(response, order_no),
                should_retry=False,
            )

        outcome = _run_with_retries(
            attempt, max_retries=_QUERY_FILL_MAX_RETRIES
        )
        return outcome.result  # type: ignore[return-value]

    def _classify_fill_response(
        self, response: Any, order_no: str
    ) -> KisFillStatusResult:
        """Map an HTTP response (200/4xx/5xx) to a KisFillStatusResult."""
        status_code = response.status_code
        if status_code >= 400 or status_code != 200:
            return KisFillStatusResult(
                success=False,
                order_no=order_no,
                filled_quantity=0,
                remaining_quantity=0,
                status="PENDING",
                message=f"UNKNOWN: KIS HTTP {status_code}",
            )
        try:
            payload = response.json()
        except (ValueError, Exception):  # noqa: BLE001
            return KisFillStatusResult(
                success=False,
                order_no=order_no,
                filled_quantity=0,
                remaining_quantity=0,
                status="PENDING",
                message="UNKNOWN: KIS HTTP 200 but body is not valid JSON",
            )
        if not isinstance(payload, dict):
            return KisFillStatusResult(
                success=False,
                order_no=order_no,
                filled_quantity=0,
                remaining_quantity=0,
                status="PENDING",
                message="UNKNOWN: KIS HTTP 200 but body is not a JSON object",
            )

        rt_cd = str(payload.get("rt_cd") or "")
        msg1 = str(payload.get("msg1") or "")[:120]
        if rt_cd != "0":
            return KisFillStatusResult(
                success=False,
                order_no=order_no,
                filled_quantity=0,
                remaining_quantity=0,
                status="PENDING",
                message=f"UNKNOWN: rt_cd={rt_cd or '?'} {msg1}".strip(),
            )

        # rt_cd == 0 — drill into output1[0] for fill quantities.
        output1 = payload.get("output1")
        record: dict[str, Any] | None = None
        if isinstance(output1, list) and output1 and isinstance(output1[0], dict):
            record = output1[0]
        elif isinstance(output1, dict):
            record = output1

        if record is None:
            # No order rows — the order has not been registered or has
            # been removed by KIS. Treat as NONE pending until a later
            # query confirms.
            return KisFillStatusResult(
                success=True,
                order_no=order_no,
                filled_quantity=0,
                remaining_quantity=0,
                status=_FILL_STATUS_MAP[FillClassification.NONE],
                message=f"NONE: {msg1}" if msg1 else "NONE",
            )

        # Whitelist: ord_qty / tot_ccld_qty / cncl_yn / rjct_yn
        try:
            ordered = int(str(record.get("ord_qty") or "0"))
        except ValueError:
            ordered = 0
        try:
            filled = int(str(record.get("tot_ccld_qty") or "0"))
        except ValueError:
            filled = 0
        cancel_flag = str(record.get("cncl_yn") or "N").upper()
        reject_flag = str(record.get("rjct_yn") or "N").upper()
        remaining = max(0, ordered - filled)

        # Order of precedence: REJECTED > CANCELED > FULL > PARTIAL > NONE.
        if reject_flag == "Y":
            cls = FillClassification.REJECTED
        elif cancel_flag == "Y":
            cls = FillClassification.CANCELED
        elif filled > 0 and filled >= ordered and ordered > 0:
            cls = FillClassification.FULL
        elif filled > 0 and filled < ordered:
            cls = FillClassification.PARTIAL
        elif filled == 0:
            cls = FillClassification.NONE
        else:
            cls = FillClassification.UNKNOWN

        return KisFillStatusResult(
            success=_FILL_SUCCESS_MAP[cls],
            order_no=order_no,
            filled_quantity=filled,
            remaining_quantity=remaining,
            status=_FILL_STATUS_MAP[cls],
            message=f"{cls}: {msg1}" if msg1 else cls,
        )

    # ----- cancel_order -------------------------------------------------

    def cancel_order(self, order_no: str) -> KisCancelResult:
        cano, acnt_prdt_cd = self._account_split()
        body: dict[str, Any] = {
            "CANO": cano,
            "ACNT_PRDT_CD": acnt_prdt_cd,
            "KRX_FWDG_ORD_ORGNO": "",
            "ORGN_ODNO": order_no,
            "ORD_DVSN": "00",
            "RVSE_CNCL_DVSN_CD": "02",  # cancel
            "ORD_QTY": "0",
            "ORD_UNPR": "0",
            "QTY_ALL_ORD_YN": "Y",
        }
        logger.debug(
            "kis_cancel_order order_no=%s payload=%s",
            order_no,
            mask_sensitive_order_payload(body),
        )

        def attempt() -> _RetryAttempt:
            try:
                response = self._client.post(
                    _CANCEL_ORDER_PATH,
                    headers=self._headers(tr_id=_TR_ID_CANCEL),
                    json=body,
                    timeout=self._settings.kis_order_cancel_timeout_s,
                )
            except self._httpx.TimeoutException as exc:
                return _RetryAttempt(
                    classification=CancelClassification.TIMEOUT,
                    result=KisCancelResult(
                        success=False,
                        order_no=order_no,
                        message=f"TIMEOUT: KIS cancel_order exceeded "
                        f"{self._settings.kis_order_cancel_timeout_s}s",
                    ),
                    should_retry=True,
                )
            except self._httpx.HTTPError as exc:
                return _RetryAttempt(
                    classification=CancelClassification.NETWORK_ERROR,
                    result=KisCancelResult(
                        success=False,
                        order_no=order_no,
                        message=f"NETWORK_ERROR: {type(exc).__name__}",
                    ),
                    should_retry=True,
                )
            return _RetryAttempt(
                classification="",
                result=self._classify_cancel_response(response, order_no),
                should_retry=False,
            )

        outcome = _run_with_retries(
            attempt, max_retries=_CANCEL_ORDER_MAX_RETRIES
        )
        return outcome.result  # type: ignore[return-value]

    def _classify_cancel_response(
        self, response: Any, order_no: str
    ) -> KisCancelResult:
        status_code = response.status_code
        if status_code >= 500:
            return KisCancelResult(
                success=False,
                order_no=order_no,
                message=f"UNKNOWN: KIS HTTP {status_code} (server error)",
            )
        if status_code >= 400:
            return KisCancelResult(
                success=False,
                order_no=order_no,
                message=f"REJECTED: KIS HTTP {status_code}",
            )
        if status_code != 200:
            return KisCancelResult(
                success=False,
                order_no=order_no,
                message=f"UNKNOWN: KIS HTTP {status_code}",
            )
        try:
            payload = response.json()
        except (ValueError, Exception):  # noqa: BLE001
            return KisCancelResult(
                success=False,
                order_no=order_no,
                message="UNKNOWN: KIS HTTP 200 but body is not valid JSON",
            )
        if not isinstance(payload, dict):
            return KisCancelResult(
                success=False,
                order_no=order_no,
                message="UNKNOWN: KIS HTTP 200 but body is not a JSON object",
            )
        rt_cd = str(payload.get("rt_cd") or "")
        msg1 = str(payload.get("msg1") or "")[:120]
        if rt_cd == "0":
            return KisCancelResult(
                success=True,
                order_no=order_no,
                message=f"CANCELED: {msg1}" if msg1 else "CANCELED",
            )
        return KisCancelResult(
            success=False,
            order_no=order_no,
            message=f"REJECTED: rt_cd={rt_cd or '?'} {msg1}".strip(),
        )

    # ----- lifecycle ----------------------------------------------------

    def close(self) -> None:
        """Close the underlying httpx client (best-effort)."""
        client = self._client
        try:
            close = getattr(client, "close", None)
            if callable(close):
                close()
        except Exception:  # noqa: BLE001 - close is best-effort
            pass


__all__ = [
    "HttpxKisOrderTransport",
    "PlaceClassification",
    "FillClassification",
    "CancelClassification",
]
