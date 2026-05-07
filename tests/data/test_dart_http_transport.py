"""v0.11 Phase A -- HttpxDartTransport tests.

The DART skeleton (v0.10 Phase B) accepted any ``DartTransport`` callable
so tests injected closures over fixture JSON.  Phase A adds the real
httpx-backed transport.  These tests verify:

* Mapping of HTTP / DART-envelope responses to ``ProviderCallResult``:
    - HTTP 200 + DART status "000" → ok(parsed_json)
    - HTTP 200 + DART status "010..101" → CLIENT_ERROR
    - HTTP 200 + DART status "800/900" → SERVER_ERROR
    - HTTP 200 + non-JSON body → UNKNOWN
    - HTTP 4xx → CLIENT_ERROR
    - HTTP 5xx → SERVER_ERROR
    - httpx.TimeoutException → TIMEOUT
    - httpx.ConnectError / TLS error → UNKNOWN
* Default-OFF guard: ``DART_ENABLED=false`` prevents both
  ``HttpxDartTransport`` instantiation by the factory and the
  ``httpx.Client`` constructor itself.
* Factory auto-injection: ``create_dart_providers(transport=None)`` with
  ``DART_ENABLED=true`` injects an ``HttpxDartTransport``; the factory
  call must NOT instantiate httpx.Client when caller passes their own
  transport (existing v0.10 behaviour preserved).
* Resilience integration: timeout flows to TIMEOUT, ``call_with_resilience``
  records the failure in the monitor, circuit breaker fast-fails after
  threshold.
* Secret discipline: ``crtfc_key`` is sent in the request URL but NEVER
  appears in any captured log message; the request URL itself is not
  logged at WARNING/ERROR level.

External network: 0 calls.  Every test uses respx to intercept httpx
requests at the transport layer.
"""

from __future__ import annotations

import logging
from decimal import Decimal
from typing import Any

import httpx
import pytest
import respx

from app.config.settings import Settings
from app.data.dart_provider import (
    DartFundamentalProvider,
    DartNotConfiguredError,
    HttpxDartTransport,
    create_dart_providers,
)
from app.data.provider_health_monitor import ProviderHealthMonitor
from app.data.provider_resilience import (
    CircuitBreakerState,
    ProviderCallResult,
    ProviderErrorKind,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


_DART_BASE_URL = "https://opendart.fss.or.kr"
_FNLTT_PATH = "/api/fnlttSinglAcnt.json"
_DART_API_KEY = "test-crtfc-key-DO-NOT-LOG-XYZ"


def _enabled_settings(
    monkeypatch: pytest.MonkeyPatch,
    *,
    timeout_s: float | None = None,
    max_attempts: int | None = None,
) -> Settings:
    """Build a Settings instance with DART opted in."""
    monkeypatch.setenv("DART_ENABLED", "true")
    monkeypatch.setenv("DART_API_KEY", _DART_API_KEY)
    monkeypatch.setenv("DART_BASE_URL", _DART_BASE_URL)
    if timeout_s is not None:
        monkeypatch.setenv("DART_TIMEOUT_S", str(timeout_s))
    if max_attempts is not None:
        monkeypatch.setenv("DART_MAX_ATTEMPTS", str(max_attempts))
    return Settings()


def _disabled_settings(monkeypatch: pytest.MonkeyPatch) -> Settings:
    monkeypatch.delenv("DART_ENABLED", raising=False)
    monkeypatch.delenv("DART_API_KEY", raising=False)
    return Settings()


_FUND_OK_PAYLOAD = {
    "status": "000",
    "message": "정상",
    "corp_name": "삼성전자",
    "list": [
        {"account_nm": "매출액", "thstrm_amount": "258,935,500"},
        {"account_nm": "영업이익", "thstrm_amount": "32,726,000"},
    ],
}


# ---------------------------------------------------------------------------
# HTTP status → ProviderCallResult
# ---------------------------------------------------------------------------


@respx.mock
def test_transport_http_200_status_000_returns_ok(
    monkeypatch: pytest.MonkeyPatch,
):
    settings = _enabled_settings(monkeypatch)
    respx.get(f"{_DART_BASE_URL}{_FNLTT_PATH}").mock(
        return_value=httpx.Response(200, json=_FUND_OK_PAYLOAD)
    )
    transport = HttpxDartTransport(settings=settings)
    try:
        result = transport(_FNLTT_PATH, {"corp_code": "005930", "crtfc_key": _DART_API_KEY})
    finally:
        transport.close()

    assert result.success is True
    assert result.value["status"] == "000"
    assert result.value["corp_name"] == "삼성전자"


@respx.mock
@pytest.mark.parametrize(
    ("dart_status", "expected_kind"),
    [
        ("010", ProviderErrorKind.CLIENT_ERROR),  # 등록되지 않은 키
        ("011", ProviderErrorKind.CLIENT_ERROR),  # 사용할 수 없는 키
        ("012", ProviderErrorKind.CLIENT_ERROR),  # 접근할 수 없는 IP
        ("013", ProviderErrorKind.CLIENT_ERROR),  # 데이터 없음
        ("020", ProviderErrorKind.CLIENT_ERROR),  # 요청 제한 초과
        ("100", ProviderErrorKind.CLIENT_ERROR),  # 필드 오류
        ("101", ProviderErrorKind.CLIENT_ERROR),  # 부적절한 접근
    ],
)
def test_transport_dart_envelope_client_codes_fail(
    monkeypatch: pytest.MonkeyPatch,
    dart_status: str,
    expected_kind: ProviderErrorKind,
):
    settings = _enabled_settings(monkeypatch)
    respx.get(f"{_DART_BASE_URL}{_FNLTT_PATH}").mock(
        return_value=httpx.Response(
            200,
            json={"status": dart_status, "message": "test"},
        )
    )
    transport = HttpxDartTransport(settings=settings)
    try:
        result = transport(_FNLTT_PATH, {"crtfc_key": _DART_API_KEY})
    finally:
        transport.close()

    assert result.success is False
    assert result.error_kind == expected_kind


@respx.mock
@pytest.mark.parametrize("dart_status", ["800", "900"])
def test_transport_dart_envelope_server_codes_fail(
    monkeypatch: pytest.MonkeyPatch,
    dart_status: str,
):
    settings = _enabled_settings(monkeypatch)
    respx.get(f"{_DART_BASE_URL}{_FNLTT_PATH}").mock(
        return_value=httpx.Response(
            200,
            json={"status": dart_status, "message": "system maintenance"},
        )
    )
    transport = HttpxDartTransport(settings=settings)
    try:
        result = transport(_FNLTT_PATH, {"crtfc_key": _DART_API_KEY})
    finally:
        transport.close()

    assert result.success is False
    assert result.error_kind == ProviderErrorKind.SERVER_ERROR


@respx.mock
def test_transport_http_4xx_returns_client_error(
    monkeypatch: pytest.MonkeyPatch,
):
    settings = _enabled_settings(monkeypatch)
    respx.get(f"{_DART_BASE_URL}{_FNLTT_PATH}").mock(
        return_value=httpx.Response(403, text="forbidden")
    )
    transport = HttpxDartTransport(settings=settings)
    try:
        result = transport(_FNLTT_PATH, {"crtfc_key": _DART_API_KEY})
    finally:
        transport.close()

    assert result.success is False
    assert result.error_kind == ProviderErrorKind.CLIENT_ERROR
    assert "403" in (result.error_message or "")


@respx.mock
def test_transport_http_5xx_returns_server_error(
    monkeypatch: pytest.MonkeyPatch,
):
    settings = _enabled_settings(monkeypatch)
    respx.get(f"{_DART_BASE_URL}{_FNLTT_PATH}").mock(
        return_value=httpx.Response(503, text="service unavailable")
    )
    transport = HttpxDartTransport(settings=settings)
    try:
        result = transport(_FNLTT_PATH, {"crtfc_key": _DART_API_KEY})
    finally:
        transport.close()

    assert result.success is False
    assert result.error_kind == ProviderErrorKind.SERVER_ERROR
    assert "503" in (result.error_message or "")


@respx.mock
def test_transport_timeout_returns_timeout(monkeypatch: pytest.MonkeyPatch):
    settings = _enabled_settings(monkeypatch, timeout_s=0.5)
    respx.get(f"{_DART_BASE_URL}{_FNLTT_PATH}").mock(
        side_effect=httpx.ReadTimeout("simulated read timeout")
    )
    transport = HttpxDartTransport(settings=settings)
    try:
        result = transport(_FNLTT_PATH, {"crtfc_key": _DART_API_KEY})
    finally:
        transport.close()

    assert result.success is False
    assert result.error_kind == ProviderErrorKind.TIMEOUT


@respx.mock
def test_transport_connect_error_returns_unknown(
    monkeypatch: pytest.MonkeyPatch,
):
    settings = _enabled_settings(monkeypatch)
    respx.get(f"{_DART_BASE_URL}{_FNLTT_PATH}").mock(
        side_effect=httpx.ConnectError("connection refused")
    )
    transport = HttpxDartTransport(settings=settings)
    try:
        result = transport(_FNLTT_PATH, {"crtfc_key": _DART_API_KEY})
    finally:
        transport.close()

    assert result.success is False
    assert result.error_kind == ProviderErrorKind.UNKNOWN


@respx.mock
def test_transport_http_200_invalid_json_returns_unknown(
    monkeypatch: pytest.MonkeyPatch,
):
    settings = _enabled_settings(monkeypatch)
    respx.get(f"{_DART_BASE_URL}{_FNLTT_PATH}").mock(
        return_value=httpx.Response(200, text="<html>not json</html>")
    )
    transport = HttpxDartTransport(settings=settings)
    try:
        result = transport(_FNLTT_PATH, {"crtfc_key": _DART_API_KEY})
    finally:
        transport.close()

    assert result.success is False
    assert result.error_kind == ProviderErrorKind.UNKNOWN
    assert "JSON" in (result.error_message or "")


@respx.mock
def test_transport_http_200_json_array_returns_unknown(
    monkeypatch: pytest.MonkeyPatch,
):
    """DART payload is always a JSON object; an array body is malformed."""
    settings = _enabled_settings(monkeypatch)
    respx.get(f"{_DART_BASE_URL}{_FNLTT_PATH}").mock(
        return_value=httpx.Response(200, json=["not", "an", "object"])
    )
    transport = HttpxDartTransport(settings=settings)
    try:
        result = transport(_FNLTT_PATH, {"crtfc_key": _DART_API_KEY})
    finally:
        transport.close()

    assert result.success is False
    assert result.error_kind == ProviderErrorKind.UNKNOWN


@respx.mock
def test_transport_http_unexpected_status_returns_unknown(
    monkeypatch: pytest.MonkeyPatch,
):
    settings = _enabled_settings(monkeypatch)
    respx.get(f"{_DART_BASE_URL}{_FNLTT_PATH}").mock(
        return_value=httpx.Response(304)
    )
    transport = HttpxDartTransport(settings=settings)
    try:
        result = transport(_FNLTT_PATH, {"crtfc_key": _DART_API_KEY})
    finally:
        transport.close()

    assert result.success is False
    assert result.error_kind == ProviderErrorKind.UNKNOWN


# ---------------------------------------------------------------------------
# Factory auto-injection
# ---------------------------------------------------------------------------


@respx.mock
def test_factory_auto_injects_httpx_transport_when_enabled(
    monkeypatch: pytest.MonkeyPatch,
):
    settings = _enabled_settings(monkeypatch)
    respx.get(f"{_DART_BASE_URL}{_FNLTT_PATH}").mock(
        return_value=httpx.Response(200, json=_FUND_OK_PAYLOAD)
    )
    monitor = ProviderHealthMonitor()
    providers = create_dart_providers(
        settings=settings, transport=None, monitor=monitor
    )
    assert set(providers) == {"fundamentals", "earnings", "disclosures"}

    out = providers["fundamentals"].fetch_fundamentals(["005930"], 2026, 1)
    assert len(out) == 1
    assert out[0].revenue == Decimal("258935500")
    assert monitor.get_status("dart")["success_count"] == 1


def test_factory_disabled_dart_does_not_instantiate_transport(
    monkeypatch: pytest.MonkeyPatch,
):
    """v0.10 zero-network guard preserved: DART_ENABLED=false short-circuits
    in ``_check_enabled`` before the factory ever asks for a transport.
    """
    settings = _disabled_settings(monkeypatch)
    # Monkeypatch httpx.Client to blow up on instantiation -- the factory
    # must NOT reach this point because _check_enabled raises first.
    monkeypatch.setattr(
        httpx,
        "Client",
        lambda *_a, **_kw: (_ for _ in ()).throw(
            AssertionError("DART_ENABLED=false but Client was instantiated")
        ),
    )
    with pytest.raises(DartNotConfiguredError):
        create_dart_providers(settings=settings, transport=None)


def test_factory_caller_supplied_transport_skips_httpx_construction(
    monkeypatch: pytest.MonkeyPatch,
):
    """When the caller passes a transport, the factory must NOT touch
    ``httpx.Client`` -- the v0.10 ``test_no_httpx_client_constructed``
    guard remains valid for the test-injected path.
    """
    settings = _enabled_settings(monkeypatch)
    monkeypatch.setattr(
        httpx,
        "Client",
        lambda *_a, **_kw: (_ for _ in ()).throw(
            AssertionError("Caller-supplied transport must skip httpx.Client")
        ),
    )

    fake_calls: list[tuple[str, dict[str, Any]]] = []

    def fake_transport(path: str, params) -> ProviderCallResult:
        fake_calls.append((path, dict(params)))
        return ProviderCallResult.ok(_FUND_OK_PAYLOAD)

    providers = create_dart_providers(
        settings=settings, transport=fake_transport
    )
    assert set(providers) == {"fundamentals", "earnings", "disclosures"}


# ---------------------------------------------------------------------------
# Resilience integration -- timeout / circuit breaker
# ---------------------------------------------------------------------------


@respx.mock
def test_provider_timeout_isolated_through_call_with_resilience(
    monkeypatch: pytest.MonkeyPatch,
):
    """Timeout via real HttpxDartTransport flows through call_with_resilience
    and arrives as TIMEOUT in the monitor; the provider returns an empty
    DTO list (no exception escapes).
    """
    settings = _enabled_settings(monkeypatch, timeout_s=0.2, max_attempts=1)
    respx.get(f"{_DART_BASE_URL}{_FNLTT_PATH}").mock(
        side_effect=httpx.ReadTimeout("simulated")
    )
    monitor = ProviderHealthMonitor()
    providers = create_dart_providers(
        settings=settings, transport=None, monitor=monitor
    )
    out = providers["fundamentals"].fetch_fundamentals(["005930"], 2026, 1)
    assert out == []
    status = monitor.get_status("dart")
    assert status["failure_count"] == 1
    assert status["last_error_kind"] == "TIMEOUT"


@respx.mock
def test_provider_circuit_breaker_fast_fails_after_threshold(
    monkeypatch: pytest.MonkeyPatch,
):
    """Repeated 5xx responses trip the circuit breaker; subsequent symbols
    short-circuit without reaching the transport.
    """
    settings = _enabled_settings(monkeypatch, max_attempts=1)
    route = respx.get(f"{_DART_BASE_URL}{_FNLTT_PATH}").mock(
        return_value=httpx.Response(503)
    )
    monitor = ProviderHealthMonitor()
    monitor.register("dart", failure_threshold=2)

    providers = create_dart_providers(
        settings=settings, transport=None, monitor=monitor
    )
    out = providers["fundamentals"].fetch_fundamentals(
        ["A", "B", "C", "D"], 2026, 1
    )
    assert out == []
    # Breaker tripped after the 2nd failure; symbols C / D never reached
    # the transport, so respx logs only 2 actual HTTP calls.
    assert route.call_count == 2
    assert monitor.get_status("dart")["status"] == CircuitBreakerState.OPEN.value


@respx.mock
def test_provider_per_symbol_failure_isolation(
    monkeypatch: pytest.MonkeyPatch,
):
    """First symbol returns 5xx, second symbol returns 200 → the second
    DTO survives; the first is silently dropped.
    """
    settings = _enabled_settings(monkeypatch, max_attempts=1)
    responses = [
        httpx.Response(503),
        httpx.Response(200, json=_FUND_OK_PAYLOAD),
    ]

    def side_effect(_request: httpx.Request) -> httpx.Response:
        return responses.pop(0)

    respx.get(f"{_DART_BASE_URL}{_FNLTT_PATH}").mock(side_effect=side_effect)

    monitor = ProviderHealthMonitor()
    providers = create_dart_providers(
        settings=settings, transport=None, monitor=monitor
    )
    out = providers["fundamentals"].fetch_fundamentals(
        ["BADCORP", "005930"], 2026, 1
    )
    assert len(out) == 1
    assert out[0].symbol == "005930"
    status = monitor.get_status("dart")
    assert status["call_count"] == 2
    assert status["success_count"] == 1
    assert status["failure_count"] == 1


# ---------------------------------------------------------------------------
# Secret discipline -- crtfc_key never appears in logs
# ---------------------------------------------------------------------------


@respx.mock
def test_transport_does_not_log_crtfc_key_on_success(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
):
    settings = _enabled_settings(monkeypatch)
    respx.get(f"{_DART_BASE_URL}{_FNLTT_PATH}").mock(
        return_value=httpx.Response(200, json=_FUND_OK_PAYLOAD)
    )
    transport = HttpxDartTransport(settings=settings)
    try:
        with caplog.at_level(logging.DEBUG):
            transport(
                _FNLTT_PATH,
                {"corp_code": "005930", "crtfc_key": _DART_API_KEY},
            )
    finally:
        transport.close()

    joined = " ".join(r.getMessage() for r in caplog.records)
    assert _DART_API_KEY not in joined
    assert "test-crtfc-key" not in joined
    # If httpx logged the URL, the key NAME may appear but the value MUST
    # be masked by the _SensitiveQueryStringFilter installed at transport
    # construction.
    if "crtfc_key=" in joined:
        assert "crtfc_key=***" in joined


@respx.mock
def test_transport_does_not_log_crtfc_key_on_failure(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
):
    settings = _enabled_settings(monkeypatch, max_attempts=1)
    respx.get(f"{_DART_BASE_URL}{_FNLTT_PATH}").mock(
        return_value=httpx.Response(500, text="dart server down")
    )
    monitor = ProviderHealthMonitor()
    providers = create_dart_providers(
        settings=settings, transport=None, monitor=monitor
    )
    with caplog.at_level(logging.DEBUG):
        providers["fundamentals"].fetch_fundamentals(["005930"], 2026, 1)

    joined = " ".join(r.getMessage() for r in caplog.records)
    assert _DART_API_KEY not in joined
    assert "test-crtfc-key" not in joined
    # Even the failure message in ProviderCallResult must not echo the key.
    status = monitor.get_status("dart")
    assert _DART_API_KEY not in (status["last_error_message"] or "")


@respx.mock
def test_transport_does_not_log_crtfc_key_on_connect_error(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
):
    """httpx exception ``__str__`` may include the request URL.  We use the
    exception class name only -- never str(exc) -- so the key cannot leak
    via that path.
    """
    settings = _enabled_settings(monkeypatch, max_attempts=1)
    # ConnectError carries the full URL in repr by default.
    respx.get(f"{_DART_BASE_URL}{_FNLTT_PATH}").mock(
        side_effect=httpx.ConnectError(
            f"Failed to establish a new connection to "
            f"{_DART_BASE_URL}{_FNLTT_PATH}?crtfc_key={_DART_API_KEY}"
        )
    )
    transport = HttpxDartTransport(settings=settings)
    try:
        with caplog.at_level(logging.DEBUG):
            result = transport(
                _FNLTT_PATH, {"crtfc_key": _DART_API_KEY}
            )
    finally:
        transport.close()

    assert result.success is False
    assert result.error_kind == ProviderErrorKind.UNKNOWN
    # The transport returns only the exception class name, never str(exc).
    assert _DART_API_KEY not in (result.error_message or "")
    joined = " ".join(r.getMessage() for r in caplog.records)
    assert _DART_API_KEY not in joined


# ---------------------------------------------------------------------------
# Real-network guard (zero httpx outbound)
# ---------------------------------------------------------------------------


@respx.mock(assert_all_called=False)
def test_no_unmocked_request_escapes(monkeypatch: pytest.MonkeyPatch):
    """respx aborts when an HTTP request is issued without a matching mock.
    This test creates the transport but issues no request -- it verifies
    that simply *constructing* HttpxDartTransport does not perform any
    network call.
    """
    settings = _enabled_settings(monkeypatch)
    transport = HttpxDartTransport(settings=settings)
    # No call, no assertion needed -- respx will fail the test on
    # teardown if any outbound HTTP slipped through during construction.
    transport.close()
