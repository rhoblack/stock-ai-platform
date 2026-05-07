"""v0.10 Phase B -- DART OpenAPI provider skeleton.

PURPOSE
-------
Wraps three DART (https://opendart.fss.or.kr) endpoints behind the existing
v0.5 / v0.6 typed provider interfaces:

* :class:`DartFundamentalProvider`  → :class:`FundamentalProviderInterface`
  (재무제표 단일 회사 ``/api/fnlttSinglAcnt.json``)
* :class:`DartEarningsProvider`     → :class:`EarningsProviderInterface`
  (매출액·영업이익 subset of ``/api/fnlttSinglAcnt.json``)
* :class:`DartDisclosureProvider`   → :class:`DisclosureProviderInterface`
  (공시 목록 ``/api/list.json``)

SCOPE (Phase B)
---------------
* No real network call is made.  The HTTP transport layer is injected: tests
  pass a callable returning fixture JSON; production wiring is deferred to
  Phase D.
* ``Settings.dart_enabled`` defaults to ``False`` -- the provider factory
  raises :class:`DartNotConfiguredError` and the scheduler / job layer skips.
* No new DB models or Alembic revision -- existing ``financial_statements``
  / ``news_items`` reuse only.
* All call boundaries go through
  :func:`app.data.provider_health_monitor.call_with_resilience` so that
  retry / circuit-breaker / failure-isolation are inherited from Phase A.

PARSER / MAPPER POLICY
----------------------
The parsers reject any field that resembles full body text:
``body / content / full_text / paragraph / raw_text / html_body / 본문 /
원문 / 전문``.  Only the following fields propagate into DTOs:

* symbol (corp short code) / company_name
* title (disclosure 제목) / disclosure_type
* source_url (DART listing URL)
* published_at
* short numeric financial fields (revenue / operating_income / ...)
* short summary (≤ 500 chars)

ERROR TAXONOMY
--------------
The HTTP transport callable maps DART responses to
:class:`~app.data.provider_resilience.ProviderCallResult`:

* HTTP 200 + ``status == "000"`` → ``ProviderCallResult.ok(parsed)``
* HTTP 200 + ``status == "010..013"`` → CLIENT_ERROR (key invalid / quota /
  permission) -- not retried.
* HTTP 200 + ``status == "020"`` → SERVER_ERROR (DART internal) -- retried.
* HTTP 4xx                          → CLIENT_ERROR
* HTTP 5xx                          → SERVER_ERROR
* network timeout                   → TIMEOUT
* anything else                     → UNKNOWN

All exceptions raised by the transport callable are caught by
``call_with_resilience`` and converted to ``ProviderCallResult.fail(UNKNOWN)``.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Any, Callable, Mapping

from app.config.settings import Settings, get_settings
from app.data.dtos import (
    DisclosureItemDTO,
    EarningsEventDTO,
    FundamentalSnapshotDTO,
)
from app.data.interfaces import (
    DisclosureProviderInterface,
    EarningsProviderInterface,
    FundamentalProviderInterface,
)
from app.data.provider_health_monitor import (
    ProviderHealthMonitor,
    call_with_resilience,
    get_health_monitor,
)
from app.data.provider_resilience import (
    ProviderCallResult,
    ProviderErrorKind,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class DartProviderError(RuntimeError):
    """Base error for DART provider problems."""


class DartNotConfiguredError(DartProviderError):
    """Raised when ``dart_enabled=False`` or the API key is missing.

    The provider factory inspects ``Settings.dart_enabled`` /
    ``Settings.dart_api_key`` *before* instantiating any provider; this error
    is the explicit signal that the operator has not opted in.  Jobs catch
    it and skip without falling back to a fake.
    """


class DartParseError(DartProviderError):
    """Raised when the parser cannot interpret a DART payload."""


# ---------------------------------------------------------------------------
# Forbidden body / full-text fields (defence in depth -- v0.5/v0.6 policy)
# ---------------------------------------------------------------------------

# Any DART payload that includes one of these keys is *truncated* by the
# parser -- the offending key is dropped before the DTO is constructed.  Tests
# assert this guard explicitly so a future schema change cannot silently leak
# disclosure body / full text into our database.
_FORBIDDEN_BODY_FIELDS: frozenset[str] = frozenset(
    {
        "body",
        "content",
        "full_text",
        "fulltext",
        "paragraph",
        "raw_text",
        "rawtext",
        "html_body",
        "html",
        "본문",
        "원문",
        "전문",
    }
)


def _strip_forbidden_fields(payload: Mapping[str, Any]) -> dict[str, Any]:
    """Return ``payload`` with any forbidden body field removed.

    Comparison is case-insensitive on the ASCII keys; Korean keys are matched
    exact-case (str.lower() leaves them unchanged).
    """
    out: dict[str, Any] = {}
    for key, value in payload.items():
        if key.lower() in _FORBIDDEN_BODY_FIELDS:
            logger.debug("dropping forbidden DART field key=%s", key)
            continue
        out[key] = value
    return out


_SUMMARY_MAX_LEN = 500


def _short_summary(text: str | None) -> str | None:
    """Truncate operator-supplied free text to ``_SUMMARY_MAX_LEN``."""
    if text is None:
        return None
    text = text.strip()
    if not text:
        return None
    if len(text) > _SUMMARY_MAX_LEN:
        return text[:_SUMMARY_MAX_LEN]
    return text


# ---------------------------------------------------------------------------
# HTTP transport contract
# ---------------------------------------------------------------------------

# A DART transport is *any* zero-arg-from-the-provider callable that takes
# (path, params) and returns ``ProviderCallResult`` whose ``value`` is the
# parsed-JSON dict from DART.  Tests pass a closure over a fixture; the
# real httpx-backed transport is added in Phase D when network use is
# permitted.
DartTransport = Callable[[str, Mapping[str, Any]], ProviderCallResult]


# ---------------------------------------------------------------------------
# DART status code → ProviderErrorKind
# ---------------------------------------------------------------------------

# DART returns a JSON envelope ``{"status": "000", "message": "정상", ...}``.
# Codes documented at https://opendart.fss.or.kr/guide/main.do (search
# "응답코드"). Subset relevant to read-only endpoints:
_DART_STATUS_OK = "000"
_DART_STATUS_NO_DATA = "013"
_DART_CLIENT_STATUSES: frozenset[str] = frozenset(
    {
        "010",  # 등록되지 않은 키
        "011",  # 사용할 수 없는 키 (만료 / 차단)
        "012",  # 접근할 수 없는 IP
        "013",  # 조회된 데이타가 없음
        "020",  # 요청 제한 초과 -- but treat as client (don't retry, back off in Phase D)
        "100",  # 필드 오류
        "101",  # 부적절한 접근
    }
)
_DART_SERVER_STATUSES: frozenset[str] = frozenset(
    {
        "800",  # 시스템 점검
        "900",  # 정의되지 않은 오류
    }
)


def classify_dart_status(status: str | None) -> ProviderErrorKind | None:
    """Return the matching ProviderErrorKind for a DART status code.

    Returns ``None`` when the code is the OK marker (``"000"``).
    Returns ``UNKNOWN`` when the code is unrecognised.
    """
    if status is None:
        return ProviderErrorKind.UNKNOWN
    if status == _DART_STATUS_OK:
        return None
    if status in _DART_SERVER_STATUSES:
        return ProviderErrorKind.SERVER_ERROR
    if status in _DART_CLIENT_STATUSES:
        return ProviderErrorKind.CLIENT_ERROR
    return ProviderErrorKind.UNKNOWN


# ---------------------------------------------------------------------------
# Numeric parsing helpers
# ---------------------------------------------------------------------------


def _to_decimal(raw: Any) -> Decimal | None:
    """Parse a DART numeric field that may be ``"258,935,500"`` or ``None``."""
    if raw is None or raw == "" or raw == "-":
        return None
    if isinstance(raw, (int, float, Decimal)):
        try:
            return Decimal(str(raw))
        except (InvalidOperation, ValueError):
            return None
    if isinstance(raw, str):
        cleaned = raw.replace(",", "").strip()
        if not cleaned:
            return None
        try:
            return Decimal(cleaned)
        except (InvalidOperation, ValueError):
            return None
    return None


def _to_int(raw: Any) -> int | None:
    val = _to_decimal(raw)
    if val is None:
        return None
    try:
        return int(val)
    except (InvalidOperation, ValueError):
        return None


# DART account name → fundamental DTO field.  Korean labels appear in the
# real ``account_nm`` field; English fallbacks are accepted to keep mock
# fixtures readable.
_FUNDAMENTAL_ACCOUNT_MAP: dict[str, str] = {
    "매출액": "revenue",
    "수익(매출액)": "revenue",
    "영업이익": "operating_income",
    "당기순이익": "net_income",
    "자산총계": "total_assets",
    "부채총계": "total_liabilities",
    "자본총계": "total_equity",
    "revenue": "revenue",
    "operating_income": "operating_income",
    "net_income": "net_income",
    "total_assets": "total_assets",
    "total_liabilities": "total_liabilities",
    "total_equity": "total_equity",
}


# ---------------------------------------------------------------------------
# Parsers
# ---------------------------------------------------------------------------


def parse_fundamentals(
    payload: Mapping[str, Any],
    *,
    symbol: str,
    snapshot_date: date,
    fiscal_year: int,
    fiscal_quarter: int | None,
) -> FundamentalSnapshotDTO:
    """Map a DART ``fnlttSinglAcnt`` JSON payload to a FundamentalSnapshotDTO.

    Only the whitelisted account names in :data:`_FUNDAMENTAL_ACCOUNT_MAP`
    are extracted; everything else is ignored.  Forbidden body fields are
    stripped *before* parsing as a defence-in-depth guard against schema
    regressions.
    """
    payload = _strip_forbidden_fields(payload)
    rows = payload.get("list") or []
    if not isinstance(rows, list):
        raise DartParseError("DART payload 'list' is not an array")

    fields: dict[str, Decimal | None] = {}
    for row in rows:
        if not isinstance(row, Mapping):
            continue
        row = _strip_forbidden_fields(row)
        account = row.get("account_nm") or row.get("account") or ""
        target = _FUNDAMENTAL_ACCOUNT_MAP.get(str(account))
        if target is None:
            continue
        # Prefer 당기 (current period) -- DART payloads expose multiple periods
        # via thstrm_amount / frmtrm_amount / bfefrmtrm_amount.
        amount = row.get("thstrm_amount") or row.get("amount") or row.get("value")
        fields[target] = _to_decimal(amount)

    return FundamentalSnapshotDTO(
        symbol=symbol,
        snapshot_date=snapshot_date,
        fiscal_year=fiscal_year,
        fiscal_quarter=fiscal_quarter,
        revenue=fields.get("revenue"),
        operating_income=fields.get("operating_income"),
        net_income=fields.get("net_income"),
        total_assets=fields.get("total_assets"),
        total_liabilities=fields.get("total_liabilities"),
        total_equity=fields.get("total_equity"),
        source="DART",
    )


def parse_earnings(
    payload: Mapping[str, Any],
    *,
    symbol: str,
    company_name: str | None,
    event_date: date,
    fiscal_year: int,
    fiscal_quarter: int | None,
    event_type: str = "FINAL",
) -> EarningsEventDTO:
    """Map a DART ``fnlttSinglAcnt`` payload subset to EarningsEventDTO.

    DART itself does not publish consensus -- those fields stay ``None`` here
    and the operator may overlay analyst-CSV consensus elsewhere.
    """
    payload = _strip_forbidden_fields(payload)
    rows = payload.get("list") or []
    if not isinstance(rows, list):
        raise DartParseError("DART payload 'list' is not an array")

    actual: dict[str, Decimal | None] = {}
    for row in rows:
        if not isinstance(row, Mapping):
            continue
        row = _strip_forbidden_fields(row)
        account = str(row.get("account_nm") or row.get("account") or "")
        if account in {"매출액", "수익(매출액)", "revenue"}:
            actual["revenue_actual"] = _to_decimal(
                row.get("thstrm_amount") or row.get("amount")
            )
        elif account in {"영업이익", "operating_income"}:
            actual["operating_income_actual"] = _to_decimal(
                row.get("thstrm_amount") or row.get("amount")
            )
        elif account in {"당기순이익", "net_income"}:
            actual["net_income_actual"] = _to_decimal(
                row.get("thstrm_amount") or row.get("amount")
            )

    return EarningsEventDTO(
        symbol=symbol,
        event_date=event_date,
        fiscal_year=fiscal_year,
        event_type=event_type,
        company_name=company_name,
        fiscal_quarter=fiscal_quarter,
        revenue_actual=actual.get("revenue_actual"),
        operating_income_actual=actual.get("operating_income_actual"),
        net_income_actual=actual.get("net_income_actual"),
        source="DART",
    )


def parse_disclosure_item(
    row: Mapping[str, Any],
) -> DisclosureItemDTO | None:
    """Map a single DART disclosure list entry to DisclosureItemDTO.

    Returns ``None`` when essential fields (rcept_no / rcept_dt / report_nm)
    are missing rather than raising -- the caller filters the list and a
    malformed row should not abort the entire fetch.
    """
    if not isinstance(row, Mapping):
        return None
    row = _strip_forbidden_fields(row)

    title = row.get("report_nm") or row.get("title")
    rcept_no = row.get("rcept_no")
    rcept_dt = row.get("rcept_dt")
    if not (title and rcept_no and rcept_dt):
        return None

    try:
        # DART rcept_dt is YYYYMMDD, optionally with HHMMSS suffix.
        rcept_str = str(rcept_dt)
        if len(rcept_str) >= 8:
            year = int(rcept_str[0:4])
            month = int(rcept_str[4:6])
            day = int(rcept_str[6:8])
            published_at = datetime(year, month, day, tzinfo=timezone.utc)
        else:
            return None
    except (ValueError, TypeError):
        return None

    symbol = row.get("stock_code") or row.get("symbol")
    if symbol is not None:
        symbol = str(symbol).strip() or None

    company = row.get("corp_name") or row.get("company_name")
    if company is not None:
        company = str(company).strip() or None

    disclosure_type = row.get("report_tp") or row.get("disclosure_type")
    if disclosure_type is not None:
        disclosure_type = str(disclosure_type).strip() or None

    source_url = (
        row.get("source_url")
        or f"https://dart.fss.or.kr/dsaf001/main.do?rcpNo={rcept_no}"
    )

    summary = _short_summary(row.get("summary"))

    return DisclosureItemDTO(
        title=str(title).strip(),
        url=source_url,
        provider="dart",
        published_at=published_at,
        symbol=symbol,
        company_name=company,
        disclosure_type=disclosure_type,
        summary=summary,
    )


def parse_disclosures(
    payload: Mapping[str, Any],
) -> list[DisclosureItemDTO]:
    """Parse the DART ``/api/list.json`` envelope into DTOs.

    Malformed rows are skipped -- the caller still gets a partial list.
    """
    payload = _strip_forbidden_fields(payload)
    rows = payload.get("list") or []
    if not isinstance(rows, list):
        raise DartParseError("DART payload 'list' is not an array")
    items: list[DisclosureItemDTO] = []
    for row in rows:
        dto = parse_disclosure_item(row)
        if dto is not None:
            items.append(dto)
    return items


# ---------------------------------------------------------------------------
# Provider base
# ---------------------------------------------------------------------------


@dataclass
class _DartConfig:
    """Snapshot of the DART runtime settings the provider needs."""

    api_key: str
    base_url: str
    timeout_s: float
    max_attempts: int
    provider_name: str

    @classmethod
    def from_settings(cls, settings: Settings) -> "_DartConfig":
        return cls(
            api_key=settings.dart_api_key,
            base_url=settings.dart_base_url,
            timeout_s=settings.dart_timeout_s,
            max_attempts=settings.dart_max_attempts,
            provider_name=settings.dart_provider_name,
        )


def _check_enabled(settings: Settings) -> None:
    """Raise :class:`DartNotConfiguredError` unless the operator opted in."""
    if not settings.dart_enabled:
        raise DartNotConfiguredError(
            "DART_ENABLED is false; refusing to instantiate DART provider"
        )
    if not settings.dart_api_key:
        raise DartNotConfiguredError("DART_API_KEY is empty; cannot call DART")


class _DartProviderBase:
    """Shared resilience + transport plumbing for the three DART providers.

    Subclasses inject:
      * ``transport`` -- a ``DartTransport`` callable returning
        ``ProviderCallResult`` whose ``value`` is the parsed JSON envelope.
      * ``monitor``   -- a ``ProviderHealthMonitor`` (the global singleton by
        default; tests pass a fresh instance to avoid cross-test state).
    """

    def __init__(
        self,
        *,
        settings: Settings | None = None,
        transport: DartTransport | None = None,
        monitor: ProviderHealthMonitor | None = None,
    ) -> None:
        self._settings = settings or get_settings()
        _check_enabled(self._settings)
        self._config = _DartConfig.from_settings(self._settings)
        if transport is None:
            raise DartNotConfiguredError(
                "DART transport is required -- the real httpx transport is "
                "deferred to Phase D; tests must inject a fixture transport."
            )
        self._transport = transport
        self._monitor = monitor or get_health_monitor()
        # Idempotent registration; reuses any existing stats for this provider.
        self._monitor.register(self._config.provider_name)

    # -- internal -----------------------------------------------------------

    def _call(
        self,
        path: str,
        params: Mapping[str, Any],
        *,
        request_id: str | None = None,
    ) -> ProviderCallResult:
        """Invoke the transport through ``call_with_resilience``.

        The DART API key is injected here so subclasses never see / log it.
        ``call_with_resilience`` swallows all exceptions and converts them
        into ``ProviderCallResult.fail(UNKNOWN)`` -- callers must check
        ``.success`` and never rely on exceptions.
        """
        full_params = dict(params)
        full_params["crtfc_key"] = self._config.api_key

        def _do() -> ProviderCallResult:
            return self._transport(path, full_params)

        return call_with_resilience(
            self._config.provider_name,
            _do,
            monitor=self._monitor,
            max_attempts=self._config.max_attempts,
            request_id=request_id,
        )


# ---------------------------------------------------------------------------
# Concrete providers
# ---------------------------------------------------------------------------


_FNLTT_SINGLE_PATH = "/api/fnlttSinglAcnt.json"
_DISCLOSURE_LIST_PATH = "/api/list.json"

# DART quarter → reprt_code (보고서 코드).
_REPRT_CODE: dict[int | None, str] = {
    1: "11013",  # 1분기 보고서
    2: "11012",  # 반기 보고서
    3: "11014",  # 3분기 보고서
    4: "11011",  # 사업보고서
    None: "11011",
}


class DartFundamentalProvider(_DartProviderBase, FundamentalProviderInterface):
    """DART OpenAPI single-statement fundamentals provider.

    Calls ``/api/fnlttSinglAcnt.json`` once per symbol and folds the results
    into FundamentalSnapshotDTO.  Failures for individual symbols are
    isolated -- the loop continues.
    """

    def fetch_fundamentals(
        self,
        symbols: list[str],
        fiscal_year: int,
        fiscal_quarter: int | None = None,
    ) -> list[FundamentalSnapshotDTO]:
        if not symbols:
            return []
        snapshot_date = date.today()
        out: list[FundamentalSnapshotDTO] = []
        reprt_code = _REPRT_CODE.get(fiscal_quarter, _REPRT_CODE[None])

        for symbol in symbols:
            params = {
                "corp_code": symbol,
                "bsns_year": str(fiscal_year),
                "reprt_code": reprt_code,
            }
            result = self._call(_FNLTT_SINGLE_PATH, params)
            if not result.success or not isinstance(result.value, Mapping):
                logger.warning(
                    "DART fundamentals fetch failed symbol=%s kind=%s",
                    symbol,
                    result.error_kind,
                )
                continue
            try:
                dto = parse_fundamentals(
                    result.value,
                    symbol=symbol,
                    snapshot_date=snapshot_date,
                    fiscal_year=fiscal_year,
                    fiscal_quarter=fiscal_quarter,
                )
            except DartParseError as exc:
                logger.warning(
                    "DART fundamentals parse error symbol=%s error=%s",
                    symbol,
                    exc,
                )
                continue
            out.append(dto)
        return out


class DartEarningsProvider(_DartProviderBase, EarningsProviderInterface):
    """DART OpenAPI earnings provider.

    Reuses the fundamentals endpoint to extract the realised
    revenue / operating_income / net_income for the most recent reporting
    period and exposes them as EarningsEventDTO.  Consensus fields stay
    ``None`` -- DART does not publish consensus.
    """

    def fetch_earnings_events(
        self,
        symbols: list[str],
        since: date | None = None,
        until: date | None = None,
        limit: int = 100,
    ) -> list[EarningsEventDTO]:
        if not symbols:
            return []
        # Earnings cycle inferred from ``until`` if supplied, else today.
        anchor = until or date.today()
        fiscal_year = anchor.year
        # Map calendar quarter → fiscal quarter (assume 캘린더 = 회계 일치).
        fiscal_quarter = ((anchor.month - 1) // 3) + 1
        reprt_code = _REPRT_CODE.get(fiscal_quarter, _REPRT_CODE[None])

        out: list[EarningsEventDTO] = []
        for symbol in symbols:
            if since is not None and anchor < since:
                continue
            params = {
                "corp_code": symbol,
                "bsns_year": str(fiscal_year),
                "reprt_code": reprt_code,
            }
            result = self._call(_FNLTT_SINGLE_PATH, params)
            if not result.success or not isinstance(result.value, Mapping):
                logger.warning(
                    "DART earnings fetch failed symbol=%s kind=%s",
                    symbol,
                    result.error_kind,
                )
                continue
            try:
                dto = parse_earnings(
                    result.value,
                    symbol=symbol,
                    company_name=str(result.value.get("corp_name") or "") or None,
                    event_date=anchor,
                    fiscal_year=fiscal_year,
                    fiscal_quarter=fiscal_quarter,
                )
            except DartParseError as exc:
                logger.warning(
                    "DART earnings parse error symbol=%s error=%s",
                    symbol,
                    exc,
                )
                continue
            out.append(dto)
            if len(out) >= limit:
                break
        return out


class DartDisclosureProvider(_DartProviderBase, DisclosureProviderInterface):
    """DART OpenAPI disclosure list provider.

    Calls ``/api/list.json`` once per fetch and returns up to ``limit``
    DisclosureItemDTOs.  ``symbols`` filtering is applied client-side because
    DART's ``corp_code`` filter requires a single corp per request -- when
    multiple symbols are passed we issue one request per symbol.
    """

    def fetch_recent_disclosures(
        self,
        *,
        symbols: list[str] | None = None,
        since: datetime | None = None,
        limit: int = 50,
    ) -> list[DisclosureItemDTO]:
        out: list[DisclosureItemDTO] = []

        targets: list[str | None] = (
            [str(s) for s in symbols] if symbols else [None]
        )

        for symbol in targets:
            params: dict[str, Any] = {"page_count": str(min(limit, 100))}
            if symbol:
                params["corp_code"] = symbol
            if since is not None:
                params["bgn_de"] = since.strftime("%Y%m%d")

            result = self._call(_DISCLOSURE_LIST_PATH, params)
            if not result.success or not isinstance(result.value, Mapping):
                logger.warning(
                    "DART disclosure fetch failed symbol=%s kind=%s",
                    symbol,
                    result.error_kind,
                )
                continue

            try:
                items = parse_disclosures(result.value)
            except DartParseError as exc:
                logger.warning(
                    "DART disclosure parse error symbol=%s error=%s",
                    symbol,
                    exc,
                )
                continue

            for item in items:
                if since is not None and item.published_at < since:
                    continue
                out.append(item)
                if len(out) >= limit:
                    return out
        return out


# ---------------------------------------------------------------------------
# v0.11 Phase A -- real httpx-backed transport implementation.
#
# The skeleton (v0.10 Phase B) accepted any callable conforming to the
# ``DartTransport`` Protocol so tests could inject closures over fixture
# JSON.  Phase A wires a production transport that issues real HTTPS
# requests to opendart.fss.or.kr -- but ONLY when the operator has set
# both ``DART_ENABLED=true`` and ``DART_API_KEY``.  When DART is disabled
# the factory keeps raising :class:`DartNotConfiguredError`, the
# httpx.Client is never instantiated, and the v0.10 zero-network guard
# (``test_no_httpx_client_constructed``) continues to hold.
#
# RESPONSE → ProviderCallResult MAPPING
# -------------------------------------
# * HTTP 200 + valid JSON + ``status == "000"`` → ``ok(parsed_json)``.
# * HTTP 200 + valid JSON + DART status code in CLIENT/SERVER table →
#   :func:`classify_dart_status` (ProviderErrorKind).
# * HTTP 200 + non-JSON / unparseable body → UNKNOWN.
# * HTTP 4xx → CLIENT_ERROR (not retried by call_with_resilience).
# * HTTP 5xx → SERVER_ERROR (retried).
# * httpx.TimeoutException → TIMEOUT.
# * any other exception → propagated, will be caught + converted by
#   ``call_with_resilience`` to ``fail(UNKNOWN)``.
#
# SECRET DISCIPLINE
# -----------------
# The DART API key is appended to query params as ``crtfc_key`` by
# ``_DartProviderBase._call`` BEFORE the transport sees it.  This module
# never logs the resolved URL or params -- only path + status.  The
# httpx ``Request`` object is kept inside the ``with`` block and never
# re-exposed.  Callers must never embed the key in log messages.
# ---------------------------------------------------------------------------


# httpx's own logger emits an INFO line per request that includes the full
# URL: ``HTTP Request: GET https://opendart.../api/...?crtfc_key=ABC...``.
# That URL carries the API key as a query parameter, so we install a small
# filter on the httpx logger that masks any sensitive query value before
# the message is emitted.  Idempotent: re-installing on the same logger
# detects the existing filter via the marker attribute.
_SENSITIVE_QS_RE = re.compile(
    r"(?P<key>crtfc_key|api_key|apikey|access_token|token|secret|password)"
    r"=(?P<val>[^&\s\"']+)",
    re.IGNORECASE,
)
_QS_MASK = "***"


class _SensitiveQueryStringFilter(logging.Filter):
    """Mask sensitive query-string values in any log message.

    We rewrite the formatted message so that ``?crtfc_key=ABC&foo=1``
    becomes ``?crtfc_key=***&foo=1`` -- the rest of the URL (host, path,
    non-secret query params) is preserved so operators can still see
    which endpoint failed.
    """

    _MARKER = "_dart_sensitive_qs_filter_installed"

    def filter(self, record: logging.LogRecord) -> bool:
        try:
            msg = record.getMessage()
        except Exception:  # noqa: BLE001 -- defensive; never block log
            return True
        if "=" not in msg:
            return True
        masked = _SENSITIVE_QS_RE.sub(rf"\g<key>={_QS_MASK}", msg)
        if masked != msg:
            record.msg = masked
            record.args = None
        return True


def _install_sensitive_qs_filter(logger_name: str) -> None:
    """Idempotently attach the sensitive-query-string filter to a logger."""
    target = logging.getLogger(logger_name)
    if getattr(target, _SensitiveQueryStringFilter._MARKER, False):
        return
    target.addFilter(_SensitiveQueryStringFilter())
    setattr(target, _SensitiveQueryStringFilter._MARKER, True)


class HttpxDartTransport:
    """Real httpx-backed transport for DART OpenAPI calls.

    Owns a single ``httpx.Client`` for the provider lifetime.  Callers
    should construct one transport per provider trio (the factory does
    this automatically).  Pass ``client=`` to inject a pre-built client
    in tests if needed; otherwise the constructor builds one with the
    settings-derived ``base_url`` / ``timeout`` / ``User-Agent``.

    Lazy import: ``httpx`` is imported inside ``__init__`` so that
    importing :mod:`app.data.dart_provider` from a process that has
    monkeypatched ``httpx.Client`` (the v0.10 no-network guard) only
    blows up when the operator actually attempts to construct the
    transport -- which requires ``DART_ENABLED=true``.  Tests that
    inject their own transport never trigger this path.
    """

    def __init__(
        self,
        *,
        settings: Settings | None = None,
        client: Any | None = None,
        user_agent: str = "stock-ai-platform/0.11 DART transport",
    ) -> None:
        self._settings = settings or get_settings()
        # Lazy import keeps module-level imports free of httpx side
        # effects (matters for the v0.10 monkeypatch guard).
        import httpx  # noqa: PLC0415

        # Install secret-masking filter on httpx's request logger BEFORE
        # building the client so the very first request line is masked.
        # Idempotent: only takes effect once per process.
        _install_sensitive_qs_filter("httpx")

        if client is None:
            client = httpx.Client(
                base_url=self._settings.dart_base_url,
                timeout=self._settings.dart_timeout_s,
                headers={"User-Agent": user_agent},
                follow_redirects=False,
            )
        self._client = client
        # Cache for module-level access to httpx exception types so that
        # tests can monkeypatch them without re-importing.
        self._httpx = httpx

    def __call__(
        self,
        path: str,
        params: Mapping[str, Any],
    ) -> ProviderCallResult:
        """Issue a single GET request and map the response.

        ``params`` already contains ``crtfc_key`` (injected by
        ``_DartProviderBase._call``); this method MUST NOT log the
        resolved URL or the params dict.
        """
        try:
            response = self._client.get(path, params=dict(params))
        except self._httpx.TimeoutException as exc:
            return ProviderCallResult.fail(
                ProviderErrorKind.TIMEOUT,
                f"DART request timed out after {self._settings.dart_timeout_s}s",
            )
        except self._httpx.HTTPError as exc:
            # Connection refused / DNS failure / TLS error / etc. --
            # treat as UNKNOWN; circuit breaker handles repeated
            # failures.  We deliberately do NOT include str(exc) in the
            # message body of ProviderCallResult -- some httpx errors
            # carry the request URL (with query string) in their repr.
            return ProviderCallResult.fail(
                ProviderErrorKind.UNKNOWN,
                f"DART transport error: {type(exc).__name__}",
            )

        status_code = response.status_code

        if status_code >= 500:
            return ProviderCallResult.fail(
                ProviderErrorKind.SERVER_ERROR,
                f"DART HTTP {status_code}",
            )
        if status_code >= 400:
            return ProviderCallResult.fail(
                ProviderErrorKind.CLIENT_ERROR,
                f"DART HTTP {status_code}",
            )
        if status_code != 200:
            return ProviderCallResult.fail(
                ProviderErrorKind.UNKNOWN,
                f"DART HTTP {status_code}",
            )

        # HTTP 200 -- decode the JSON envelope.
        try:
            payload = response.json()
        except ValueError:
            return ProviderCallResult.fail(
                ProviderErrorKind.UNKNOWN,
                "DART HTTP 200 but body is not valid JSON",
            )

        if not isinstance(payload, Mapping):
            return ProviderCallResult.fail(
                ProviderErrorKind.UNKNOWN,
                "DART HTTP 200 but body is not a JSON object",
            )

        dart_status = payload.get("status")
        kind = classify_dart_status(
            str(dart_status) if dart_status is not None else None
        )
        if kind is None:
            # status == "000" -- success.
            return ProviderCallResult.ok(payload)

        # DART returned an envelope error code.  ``message`` is a short
        # human-readable label like "정상" / "사용할 수 없는 키" -- safe
        # to surface (no secret content), but we still keep it short.
        message = str(payload.get("message") or dart_status or "")[:120]
        return ProviderCallResult.fail(
            kind,
            f"DART status={dart_status} message={message}",
        )

    def close(self) -> None:
        """Release the underlying httpx.Client (idempotent)."""
        try:
            self._client.close()
        except Exception:  # noqa: BLE001
            pass

    def __del__(self) -> None:  # pragma: no cover -- GC-time cleanup
        self.close()


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------


def _default_transport(settings: Settings) -> "HttpxDartTransport":
    """Construct the production httpx transport.

    Separated so tests can monkeypatch the factory's ``transport=None``
    branch without touching the real ``HttpxDartTransport.__init__``
    side effects.
    """
    return HttpxDartTransport(settings=settings)


def create_dart_providers(
    *,
    settings: Settings | None = None,
    transport: DartTransport | None = None,
    monitor: ProviderHealthMonitor | None = None,
) -> dict[str, _DartProviderBase]:
    """Construct the three DART providers in one call.

    Raises :class:`DartNotConfiguredError` immediately when the operator has
    not opted in, so the scheduler / job layer can short-circuit without
    leaking partial state.

    v0.11 Phase A: when ``transport=None`` and the operator has set
    ``DART_ENABLED=true`` + ``DART_API_KEY``, the factory auto-injects
    :class:`HttpxDartTransport`.  Tests that pass their own transport
    keep the v0.10 zero-network behaviour.
    """
    settings = settings or get_settings()
    _check_enabled(settings)
    if transport is None:
        transport = _default_transport(settings)
    return {
        "fundamentals": DartFundamentalProvider(
            settings=settings, transport=transport, monitor=monitor
        ),
        "earnings": DartEarningsProvider(
            settings=settings, transport=transport, monitor=monitor
        ),
        "disclosures": DartDisclosureProvider(
            settings=settings, transport=transport, monitor=monitor
        ),
    }


__all__ = [
    "DartProviderError",
    "DartNotConfiguredError",
    "DartParseError",
    "DartFundamentalProvider",
    "DartEarningsProvider",
    "DartDisclosureProvider",
    "DartTransport",
    "HttpxDartTransport",
    "classify_dart_status",
    "create_dart_providers",
    "parse_disclosure_item",
    "parse_disclosures",
    "parse_earnings",
    "parse_fundamentals",
]
