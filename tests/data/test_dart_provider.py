"""v0.10 Phase B -- DART provider skeleton tests.

Coverage:

* Settings: ``dart_enabled`` defaults False; ``dart_api_key`` defaults empty;
  ``dart_base_url`` / ``dart_timeout_s`` / ``dart_max_attempts`` /
  ``dart_provider_name`` defaults present.
* ``DART_ENABLED=false`` → ``DartNotConfiguredError`` (no instantiation,
  no transport call).
* DART status → ProviderErrorKind mapping (000 / 010..013 / 020 / 800 / 900 /
  unknown).
* Mock-fixture parser tests for ``fnlttSinglAcnt`` (fundamentals + earnings
  subset) and ``list`` (disclosures).
* Forbidden body fields (body / content / full_text / raw_text / paragraph /
  본문 / 원문 / 전문) are stripped *before* the DTO is built.
* Malformed responses (missing ``list``, non-dict rows, missing rcept_no,
  bad rcept_dt, empty list) -- partial / empty results, no exceptions
  reach the caller.
* Timeout / SERVER_ERROR / CLIENT_ERROR transport responses propagate as
  ``ProviderCallResult.fail`` -- no exception escapes; symbol fetch loop
  continues.
* Circuit breaker trips after repeated failures and fast-fails subsequent
  symbols.
* The ``crtfc_key`` query parameter is injected by the provider but never
  appears in any log message; ``SensitiveFilter`` masks ``dart_api_key`` /
  ``DART_API_KEY`` / ``crtfc_key`` extra fields.
* DTO body-field discipline: returned DTOs never carry body / full_text /
  paragraph attributes (verified by ``dataclasses.fields``).
* ``call_with_resilience`` is invoked for every transport call (verified
  via the global health-monitor counters).
* No real httpx / network call is made (no ``httpx.Client`` is constructed).
"""

from __future__ import annotations

import logging
from dataclasses import fields as dc_fields
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Any, Mapping

import pytest

from app.config.logging import SensitiveFilter, _MASK
from app.config.settings import Settings
from app.data.dart_provider import (
    DartDisclosureProvider,
    DartEarningsProvider,
    DartFundamentalProvider,
    DartNotConfiguredError,
    DartParseError,
    classify_dart_status,
    create_dart_providers,
    parse_disclosure_item,
    parse_disclosures,
    parse_earnings,
    parse_fundamentals,
)
from app.data.dtos import DisclosureItemDTO, EarningsEventDTO, FundamentalSnapshotDTO
from app.data.provider_health_monitor import ProviderHealthMonitor
from app.data.provider_resilience import (
    ProviderCallResult,
    ProviderErrorKind,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _enabled_settings(monkeypatch: pytest.MonkeyPatch) -> Settings:
    """Build a Settings instance with DART opted in via a fresh env."""
    monkeypatch.setenv("DART_ENABLED", "true")
    monkeypatch.setenv("DART_API_KEY", "test-crtfc-key-XXXXXXXX")
    return Settings()


def _disabled_settings(monkeypatch: pytest.MonkeyPatch) -> Settings:
    """Build a Settings instance with DART explicitly off."""
    monkeypatch.delenv("DART_ENABLED", raising=False)
    monkeypatch.delenv("DART_API_KEY", raising=False)
    return Settings()


def _record_calls(responses: list[ProviderCallResult]):
    """Return a ``DartTransport`` callable that pops responses in order.

    Records each (path, params) for assertion.  Raises ``RuntimeError`` if
    called more times than there are responses; tests that need an
    indefinitely-failing transport should pass a longer list.
    """
    calls: list[tuple[str, dict[str, Any]]] = []
    queue = list(responses)

    def transport(path: str, params: Mapping[str, Any]) -> ProviderCallResult:
        calls.append((path, dict(params)))
        if not queue:
            raise RuntimeError("no more queued responses")
        return queue.pop(0)

    return transport, calls


# ---------------------------------------------------------------------------
# Mock fixtures (DART OpenAPI shape, no real network)
# ---------------------------------------------------------------------------


_FUND_FIXTURE_SAMSUNG = {
    "status": "000",
    "message": "정상",
    "corp_name": "삼성전자",
    "list": [
        {
            "account_nm": "매출액",
            "thstrm_amount": "258,935,500",
            "frmtrm_amount": "230,000,000",
        },
        {
            "account_nm": "영업이익",
            "thstrm_amount": "32,726,000",
            "frmtrm_amount": "20,000,000",
        },
        {
            "account_nm": "당기순이익",
            "thstrm_amount": "34,451,000",
        },
        {
            "account_nm": "자산총계",
            "thstrm_amount": "455,905,000",
        },
        {
            "account_nm": "부채총계",
            "thstrm_amount": "112,334,000",
        },
        {
            "account_nm": "자본총계",
            "thstrm_amount": "343,571,000",
        },
        # Unknown account -- ignored by the parser.
        {"account_nm": "자본금", "thstrm_amount": "778,047"},
    ],
}


_DISCLOSURE_FIXTURE = {
    "status": "000",
    "message": "정상",
    "list": [
        {
            "rcept_no": "20260430000001",
            "rcept_dt": "20260430",
            "report_nm": "삼성전자 1분기 잠정 실적",
            "corp_name": "삼성전자",
            "stock_code": "005930",
            "report_tp": "주요사항보고서",
        },
        {
            "rcept_no": "20260425000033",
            "rcept_dt": "20260425",
            "report_nm": "SK하이닉스 최대주주 지분 변동",
            "corp_name": "SK하이닉스",
            "stock_code": "000660",
            "report_tp": "주식등의대량보유상황보고서",
        },
        # Malformed -- missing rcept_no.  Parser must skip without raising.
        {
            "rcept_dt": "20260420",
            "report_nm": "Bad row",
        },
        # Malformed -- bad rcept_dt.  Parser must skip.
        {
            "rcept_no": "X",
            "rcept_dt": "not-a-date",
            "report_nm": "Bad date row",
        },
    ],
}


# ---------------------------------------------------------------------------
# Settings defaults
# ---------------------------------------------------------------------------


def test_settings_dart_enabled_defaults_false(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("DART_ENABLED", raising=False)
    s = Settings()
    assert s.dart_enabled is False


def test_settings_dart_api_key_defaults_empty(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("DART_API_KEY", raising=False)
    s = Settings()
    assert s.dart_api_key == ""


def test_settings_dart_runtime_defaults(monkeypatch: pytest.MonkeyPatch):
    for var in (
        "DART_BASE_URL",
        "DART_TIMEOUT_S",
        "DART_MAX_ATTEMPTS",
        "DART_PROVIDER_NAME",
    ):
        monkeypatch.delenv(var, raising=False)
    s = Settings()
    assert s.dart_base_url == "https://opendart.fss.or.kr"
    assert s.dart_timeout_s == 10.0
    assert s.dart_max_attempts == 3
    assert s.dart_provider_name == "dart"


# ---------------------------------------------------------------------------
# Disabled / not-configured guard
# ---------------------------------------------------------------------------


def test_disabled_dart_raises_not_configured(monkeypatch: pytest.MonkeyPatch):
    settings = _disabled_settings(monkeypatch)
    transport, calls = _record_calls([])
    with pytest.raises(DartNotConfiguredError):
        DartFundamentalProvider(settings=settings, transport=transport)
    assert calls == []  # transport was NEVER called


def test_disabled_dart_factory_raises(monkeypatch: pytest.MonkeyPatch):
    settings = _disabled_settings(monkeypatch)
    transport, _calls = _record_calls([])
    with pytest.raises(DartNotConfiguredError):
        create_dart_providers(settings=settings, transport=transport)


def test_enabled_but_no_api_key_raises(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("DART_ENABLED", "true")
    monkeypatch.setenv("DART_API_KEY", "")
    settings = Settings()
    transport, _calls = _record_calls([])
    with pytest.raises(DartNotConfiguredError):
        DartFundamentalProvider(settings=settings, transport=transport)


def test_enabled_without_transport_raises(monkeypatch: pytest.MonkeyPatch):
    settings = _enabled_settings(monkeypatch)
    with pytest.raises(DartNotConfiguredError):
        DartFundamentalProvider(settings=settings, transport=None)


# ---------------------------------------------------------------------------
# DART status → ProviderErrorKind
# ---------------------------------------------------------------------------


def test_classify_dart_status_ok():
    assert classify_dart_status("000") is None


@pytest.mark.parametrize("code", ["010", "011", "012", "013", "020", "100", "101"])
def test_classify_dart_status_client(code: str):
    assert classify_dart_status(code) is ProviderErrorKind.CLIENT_ERROR


@pytest.mark.parametrize("code", ["800", "900"])
def test_classify_dart_status_server(code: str):
    assert classify_dart_status(code) is ProviderErrorKind.SERVER_ERROR


def test_classify_dart_status_unknown():
    assert classify_dart_status("ZZZ") is ProviderErrorKind.UNKNOWN
    assert classify_dart_status(None) is ProviderErrorKind.UNKNOWN


# ---------------------------------------------------------------------------
# Parsers
# ---------------------------------------------------------------------------


def test_parse_fundamentals_happy_path():
    dto = parse_fundamentals(
        _FUND_FIXTURE_SAMSUNG,
        symbol="005930",
        snapshot_date=date(2026, 5, 7),
        fiscal_year=2026,
        fiscal_quarter=1,
    )
    assert isinstance(dto, FundamentalSnapshotDTO)
    assert dto.symbol == "005930"
    assert dto.revenue == Decimal("258935500")
    assert dto.operating_income == Decimal("32726000")
    assert dto.net_income == Decimal("34451000")
    assert dto.total_assets == Decimal("455905000")
    assert dto.total_liabilities == Decimal("112334000")
    assert dto.total_equity == Decimal("343571000")
    assert dto.source == "DART"
    # 자본금 was not in the whitelist -- nothing leaked
    assert dto.eps is None
    assert dto.bps is None


def test_parse_fundamentals_missing_list_raises():
    with pytest.raises(DartParseError):
        parse_fundamentals(
            {"status": "000", "list": "not-an-array"},
            symbol="005930",
            snapshot_date=date(2026, 5, 7),
            fiscal_year=2026,
            fiscal_quarter=1,
        )


def test_parse_fundamentals_strips_forbidden_fields():
    payload = {
        "status": "000",
        "body": "<html>full disclosure body should be stripped</html>",
        "본문": "원문 전체",
        "list": [
            {
                "account_nm": "매출액",
                "thstrm_amount": "1,000",
                "full_text": "should be dropped",
                "원문": "should also be dropped",
            }
        ],
    }
    dto = parse_fundamentals(
        payload,
        symbol="005930",
        snapshot_date=date(2026, 5, 7),
        fiscal_year=2026,
        fiscal_quarter=1,
    )
    assert dto.revenue == Decimal("1000")
    # The DTO has no body-style fields by construction:
    field_names = {f.name for f in dc_fields(dto)}
    forbidden = {
        "body",
        "content",
        "full_text",
        "paragraph",
        "raw_text",
        "html_body",
        "본문",
        "원문",
        "전문",
    }
    assert forbidden.isdisjoint(field_names)


def test_parse_earnings_happy_path():
    dto = parse_earnings(
        _FUND_FIXTURE_SAMSUNG,
        symbol="005930",
        company_name="삼성전자",
        event_date=date(2026, 4, 30),
        fiscal_year=2026,
        fiscal_quarter=1,
    )
    assert isinstance(dto, EarningsEventDTO)
    assert dto.revenue_actual == Decimal("258935500")
    assert dto.operating_income_actual == Decimal("32726000")
    assert dto.net_income_actual == Decimal("34451000")
    # DART does not publish consensus; those stay None.
    assert dto.revenue_consensus is None
    assert dto.operating_income_consensus is None


def test_parse_disclosures_happy_path():
    items = parse_disclosures(_DISCLOSURE_FIXTURE)
    # 2 valid + 2 malformed (skipped) = 2 returned
    assert len(items) == 2
    titles = [d.title for d in items]
    assert "삼성전자 1분기 잠정 실적" in titles
    assert "SK하이닉스 최대주주 지분 변동" in titles
    for item in items:
        assert isinstance(item, DisclosureItemDTO)
        assert item.provider == "dart"
        assert item.url.startswith("https://")
        assert item.published_at.tzinfo is timezone.utc


def test_parse_disclosure_item_returns_none_for_malformed():
    assert parse_disclosure_item({"rcept_no": "x"}) is None  # missing rcept_dt
    assert parse_disclosure_item({"rcept_dt": "20260101"}) is None  # missing title
    assert parse_disclosure_item("not a dict") is None  # type: ignore[arg-type]


def test_parse_disclosure_item_default_source_url():
    dto = parse_disclosure_item(
        {
            "rcept_no": "20260101000001",
            "rcept_dt": "20260101",
            "report_nm": "Test report",
        }
    )
    assert dto is not None
    assert "rcpNo=20260101000001" in dto.url


def test_parse_disclosures_empty_list():
    assert parse_disclosures({"status": "000", "list": []}) == []


def test_parse_disclosures_missing_list_raises():
    with pytest.raises(DartParseError):
        parse_disclosures({"status": "000", "list": "oops"})


def test_parse_disclosures_strips_forbidden_fields():
    payload = {
        "status": "000",
        "list": [
            {
                "rcept_no": "20260101000001",
                "rcept_dt": "20260101",
                "report_nm": "Title",
                "stock_code": "005930",
                "원문": "전문",
                "body": "should be stripped",
                "full_text": "should also be stripped",
            }
        ],
    }
    items = parse_disclosures(payload)
    assert len(items) == 1
    # DTO has no body-shaped attrs:
    field_names = {f.name for f in dc_fields(items[0])}
    assert "body" not in field_names
    assert "full_text" not in field_names
    assert "본문" not in field_names


# ---------------------------------------------------------------------------
# Provider integration -- transport injection + monitor wiring
# ---------------------------------------------------------------------------


def test_fundamental_provider_calls_transport_with_api_key(
    monkeypatch: pytest.MonkeyPatch,
):
    settings = _enabled_settings(monkeypatch)
    transport, calls = _record_calls(
        [ProviderCallResult.ok(_FUND_FIXTURE_SAMSUNG)]
    )
    monitor = ProviderHealthMonitor()
    provider = DartFundamentalProvider(
        settings=settings, transport=transport, monitor=monitor
    )
    out = provider.fetch_fundamentals(["005930"], 2026, 1)

    assert len(out) == 1
    assert out[0].revenue == Decimal("258935500")
    # The API key is injected into params -- transport saw it -- but logs
    # never emit the value (verified separately).
    assert calls[0][0] == "/api/fnlttSinglAcnt.json"
    assert calls[0][1]["crtfc_key"] == "test-crtfc-key-XXXXXXXX"
    # call_with_resilience recorded the success in the monitor
    assert monitor.get_status("dart")["success_count"] == 1


def test_fundamental_provider_isolates_failed_symbols(
    monkeypatch: pytest.MonkeyPatch,
):
    settings = _enabled_settings(monkeypatch)
    transport, _calls = _record_calls(
        [
            ProviderCallResult.fail(ProviderErrorKind.SERVER_ERROR, "503"),
            ProviderCallResult.ok(_FUND_FIXTURE_SAMSUNG),
        ]
    )
    monitor = ProviderHealthMonitor()
    # max_attempts=1 in env so the single failure isn't retried away.
    monkeypatch.setenv("DART_MAX_ATTEMPTS", "1")
    settings = Settings()  # rebuild after env change
    monkeypatch.setenv("DART_ENABLED", "true")
    monkeypatch.setenv("DART_API_KEY", "test-crtfc-key-XXXXXXXX")
    settings = Settings()
    provider = DartFundamentalProvider(
        settings=settings, transport=transport, monitor=monitor
    )
    out = provider.fetch_fundamentals(["BADCORP", "005930"], 2026, 1)
    # First symbol failed → skipped; second succeeded.
    assert len(out) == 1
    assert out[0].symbol == "005930"
    status = monitor.get_status("dart")
    assert status["call_count"] == 2
    assert status["failure_count"] == 1
    assert status["success_count"] == 1


def test_fundamental_provider_timeout_isolated(monkeypatch: pytest.MonkeyPatch):
    settings = _enabled_settings(monkeypatch)
    monkeypatch.setenv("DART_MAX_ATTEMPTS", "1")
    settings = Settings()
    monkeypatch.setenv("DART_ENABLED", "true")
    monkeypatch.setenv("DART_API_KEY", "test-crtfc-key-XXXXXXXX")
    settings = Settings()
    transport, _calls = _record_calls(
        [ProviderCallResult.fail(ProviderErrorKind.TIMEOUT, "timeout")]
    )
    monitor = ProviderHealthMonitor()
    provider = DartFundamentalProvider(
        settings=settings, transport=transport, monitor=monitor
    )
    out = provider.fetch_fundamentals(["005930"], 2026, 1)
    # Timeout → empty list, no exception escapes.
    assert out == []
    status = monitor.get_status("dart")
    assert status["failure_count"] == 1
    assert status["last_error_kind"] == "TIMEOUT"


def test_fundamental_provider_exception_in_transport_isolated(
    monkeypatch: pytest.MonkeyPatch,
):
    settings = _enabled_settings(monkeypatch)
    monkeypatch.setenv("DART_MAX_ATTEMPTS", "1")
    monkeypatch.setenv("DART_ENABLED", "true")
    monkeypatch.setenv("DART_API_KEY", "test-crtfc-key-XXXXXXXX")
    settings = Settings()

    def boom(_path: str, _params: Mapping[str, Any]) -> ProviderCallResult:
        raise RuntimeError("connection reset")

    monitor = ProviderHealthMonitor()
    provider = DartFundamentalProvider(
        settings=settings, transport=boom, monitor=monitor
    )
    # Must NOT raise -- failure isolation.
    out = provider.fetch_fundamentals(["005930"], 2026, 1)
    assert out == []
    status = monitor.get_status("dart")
    assert status["failure_count"] == 1
    assert status["last_error_kind"] == "UNKNOWN"


def test_fundamental_provider_circuit_breaker_trips(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("DART_ENABLED", "true")
    monkeypatch.setenv("DART_API_KEY", "test-crtfc-key-XXXXXXXX")
    monkeypatch.setenv("DART_MAX_ATTEMPTS", "1")
    settings = Settings()

    transport_calls: list[str] = []

    def fail_transport(path: str, params: Mapping[str, Any]) -> ProviderCallResult:
        transport_calls.append(params.get("corp_code", "?"))
        return ProviderCallResult.fail(ProviderErrorKind.SERVER_ERROR, "down")

    monitor = ProviderHealthMonitor()
    monitor.register("dart", failure_threshold=2)
    provider = DartFundamentalProvider(
        settings=settings, transport=fail_transport, monitor=monitor
    )

    # 4 symbols, breaker trips after 2 failures, remaining 2 fast-fail
    # without ever calling the transport.
    out = provider.fetch_fundamentals(["A", "B", "C", "D"], 2026, 1)
    assert out == []
    assert transport_calls == ["A", "B"]  # C / D never reached transport
    assert monitor.get_status("dart")["status"] == "OPEN"


def test_earnings_provider_parses_real_actual_only(
    monkeypatch: pytest.MonkeyPatch,
):
    settings = _enabled_settings(monkeypatch)
    transport, _calls = _record_calls(
        [ProviderCallResult.ok(_FUND_FIXTURE_SAMSUNG)]
    )
    monitor = ProviderHealthMonitor()
    provider = DartEarningsProvider(
        settings=settings, transport=transport, monitor=monitor
    )
    out = provider.fetch_earnings_events(["005930"], until=date(2026, 4, 30))
    assert len(out) == 1
    assert out[0].operating_income_actual == Decimal("32726000")
    assert out[0].operating_income_consensus is None
    assert out[0].source == "DART"
    assert out[0].company_name == "삼성전자"


def test_disclosure_provider_filters_since(monkeypatch: pytest.MonkeyPatch):
    settings = _enabled_settings(monkeypatch)
    transport, _calls = _record_calls(
        [ProviderCallResult.ok(_DISCLOSURE_FIXTURE)]
    )
    monitor = ProviderHealthMonitor()
    provider = DartDisclosureProvider(
        settings=settings, transport=transport, monitor=monitor
    )
    cutoff = datetime(2026, 4, 28, tzinfo=timezone.utc)
    out = provider.fetch_recent_disclosures(since=cutoff, limit=10)
    # Only 005930 (2026-04-30) survives the cutoff.
    assert len(out) == 1
    assert out[0].symbol == "005930"


def test_disclosure_provider_per_symbol_request(monkeypatch: pytest.MonkeyPatch):
    settings = _enabled_settings(monkeypatch)
    transport, calls = _record_calls(
        [
            ProviderCallResult.ok(
                {
                    "status": "000",
                    "list": [_DISCLOSURE_FIXTURE["list"][0]],
                }
            ),
            ProviderCallResult.ok(
                {
                    "status": "000",
                    "list": [_DISCLOSURE_FIXTURE["list"][1]],
                }
            ),
        ]
    )
    monitor = ProviderHealthMonitor()
    provider = DartDisclosureProvider(
        settings=settings, transport=transport, monitor=monitor
    )
    out = provider.fetch_recent_disclosures(symbols=["005930", "000660"], limit=10)
    assert {d.symbol for d in out} == {"005930", "000660"}
    assert calls[0][1]["corp_code"] == "005930"
    assert calls[1][1]["corp_code"] == "000660"


def test_factory_creates_three_providers(monkeypatch: pytest.MonkeyPatch):
    settings = _enabled_settings(monkeypatch)
    transport, _calls = _record_calls([])
    monitor = ProviderHealthMonitor()
    providers = create_dart_providers(
        settings=settings, transport=transport, monitor=monitor
    )
    assert set(providers) == {"fundamentals", "earnings", "disclosures"}
    assert isinstance(providers["fundamentals"], DartFundamentalProvider)
    assert isinstance(providers["earnings"], DartEarningsProvider)
    assert isinstance(providers["disclosures"], DartDisclosureProvider)


# ---------------------------------------------------------------------------
# DTO body-field discipline
# ---------------------------------------------------------------------------


_BODY_FIELD_NAMES = {
    "body",
    "content",
    "full_text",
    "fulltext",
    "paragraph",
    "raw_text",
    "rawtext",
    "html_body",
    "본문",
    "원문",
    "전문",
}


@pytest.mark.parametrize(
    "dto_cls", [FundamentalSnapshotDTO, EarningsEventDTO, DisclosureItemDTO]
)
def test_dtos_have_no_body_fields(dto_cls):
    names = {f.name for f in dc_fields(dto_cls)}
    overlap = names & _BODY_FIELD_NAMES
    assert not overlap, f"{dto_cls.__name__} carries forbidden body field(s): {overlap}"


# ---------------------------------------------------------------------------
# SensitiveFilter masking for DART key variants
# ---------------------------------------------------------------------------


def _make_record(extra: dict[str, Any]) -> logging.LogRecord:
    record = logging.LogRecord("t", logging.INFO, "", 0, "msg", (), None)
    for k, v in extra.items():
        setattr(record, k, v)
    return record


@pytest.mark.parametrize(
    "field_name",
    [
        "dart_api_key",
        "DART_API_KEY",
        "crtfc_key",
        "CRTFC_KEY",
        "crtfckey",
        "dart_key",
    ],
)
def test_sensitive_filter_masks_dart_key_variants(field_name: str):
    f = SensitiveFilter()
    rec = _make_record({field_name: "test-crtfc-key-VERYSECRET"})
    f.filter(rec)
    assert getattr(rec, field_name) == _MASK


def test_sensitive_filter_does_not_mask_dart_safe_fields():
    # base_url / corp_code / report_nm should never trigger masking.
    f = SensitiveFilter()
    rec = _make_record(
        {
            "dart_base_url": "https://opendart.fss.or.kr",
            "corp_code": "005930",
            "report_nm": "1분기 보고서",
        }
    )
    f.filter(rec)
    assert rec.dart_base_url == "https://opendart.fss.or.kr"
    assert rec.corp_code == "005930"
    assert rec.report_nm == "1분기 보고서"


def test_provider_log_does_not_emit_api_key(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
):
    """Even though the transport receives ``crtfc_key``, the log statements
    emitted by the provider boundary must not mention the key value.
    """
    settings = _enabled_settings(monkeypatch)
    monkeypatch.setenv("DART_MAX_ATTEMPTS", "1")
    monkeypatch.setenv("DART_ENABLED", "true")
    monkeypatch.setenv("DART_API_KEY", "SUPER-SECRET-KEY-DO-NOT-LOG")
    settings = Settings()

    def fail_transport(path: str, params: Mapping[str, Any]) -> ProviderCallResult:
        return ProviderCallResult.fail(ProviderErrorKind.SERVER_ERROR, "boom")

    monitor = ProviderHealthMonitor()
    provider = DartFundamentalProvider(
        settings=settings, transport=fail_transport, monitor=monitor
    )
    with caplog.at_level(logging.DEBUG):
        provider.fetch_fundamentals(["005930"], 2026, 1)

    joined = " ".join(r.getMessage() for r in caplog.records)
    assert "SUPER-SECRET-KEY-DO-NOT-LOG" not in joined


# ---------------------------------------------------------------------------
# No-network guard
# ---------------------------------------------------------------------------


def test_no_httpx_client_constructed(monkeypatch: pytest.MonkeyPatch):
    """Constructing a DART provider must not import / instantiate httpx.Client.

    Phase B ships a transport-injection model only -- the real httpx
    transport is deferred to Phase D.  We monkeypatch httpx.Client to raise
    when constructed and confirm no DART code path triggers it.
    """
    settings = _enabled_settings(monkeypatch)

    import httpx as _httpx  # noqa: PLC0415

    def boom(*_a: Any, **_kw: Any):
        raise AssertionError("DART provider must not construct httpx.Client")

    monkeypatch.setattr(_httpx, "Client", boom)
    transport, _calls = _record_calls([ProviderCallResult.ok(_FUND_FIXTURE_SAMSUNG)])
    monitor = ProviderHealthMonitor()
    provider = DartFundamentalProvider(
        settings=settings, transport=transport, monitor=monitor
    )
    provider.fetch_fundamentals(["005930"], 2026, 1)
