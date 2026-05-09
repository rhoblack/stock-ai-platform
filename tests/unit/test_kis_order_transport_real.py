"""Unit tests for v1.0 Phase B — HttpxKisOrderTransport.

Hard guarantees verified by this suite
--------------------------------------
* No real KIS API call is ever made — every test that exercises the
  transport's HTTP path uses a ``respx``-mocked transport injected via
  ``client=httpx.Client(transport=respx.MockTransport(...))`` OR a
  hand-rolled fake client whose call counters are inspected directly.
* Module-level ``import`` of ``httpx`` is forbidden — verified by AST
  walk on ``kis_order_transport_real.py`` source.
* ``requests`` / ``urllib`` import is forbidden — verified by AST walk.
* No ``app.providers.kis`` / ``app.data.collectors.kis_client`` import.
* Sensitive credentials (``app_key`` / ``app_secret`` / ``access_token``
  / ``account_no``) NEVER appear in ``__repr__`` / ``str()`` /
  ``as_dict()`` / log messages.
* Raw KIS response is never returned — every result is a freshly
  constructed dataclass with whitelisted fields only.
* ``place_order`` retries 0 times on transient failure (duplicate-fill
  risk).
* ``query_fill_status`` and ``cancel_order`` retry up to 2 times on
  TimeoutException / NetworkError.
"""

from __future__ import annotations

import ast
import logging
import pathlib

import httpx
import pytest
import respx

from app.broker.kis_order_client import (
    KisCancelResult,
    KisFillStatusResult,
    KisOrderClientInterface,
    KisOrderRequest,
    KisOrderResult,
)
from app.broker.kis_order_transport_real import (
    CancelClassification,
    FillClassification,
    HttpxKisOrderTransport,
    PlaceClassification,
    _RetryAttempt,
    _run_with_retries,
)
from app.config.settings import Settings


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

# Use the paper VTS host so any accidental real call would land on a paper
# account rather than the production money endpoint.
_TEST_BASE = "https://openapivts.koreainvestment.com:29443"


def _module_source() -> str:
    here = pathlib.Path(__file__).resolve().parents[2]
    return (here / "app" / "broker" / "kis_order_transport_real.py").read_text(
        encoding="utf-8"
    )


def _settings_for_test(**overrides) -> Settings:
    """Build Settings with overrides applied. Default values keep the
    paranoid v0.16 / v1.0 caps so test never accidentally gates on
    real-trading enabled flags."""
    base = dict(
        kis_order_base_url=_TEST_BASE,
        kis_order_place_timeout_s=5.0,
        kis_order_query_timeout_s=10.0,
        kis_order_cancel_timeout_s=5.0,
    )
    base.update(overrides)
    return Settings(**base)


def _build_transport(
    *,
    mock_transport: httpx.MockTransport,
    settings: Settings | None = None,
    **transport_kwargs,
) -> HttpxKisOrderTransport:
    """Build an HttpxKisOrderTransport whose underlying httpx.Client uses
    the supplied mock transport — guarantees zero outbound traffic."""
    s = settings or _settings_for_test()
    client = httpx.Client(
        base_url=s.kis_order_base_url,
        transport=mock_transport,
        timeout=10.0,
    )
    return HttpxKisOrderTransport(
        settings=s,
        client=client,
        app_key="kis-app-key-XYZ123",
        app_secret="kis-app-secret-XYZ123ABCDEF",
        access_token="kis-access-token-XYZ123",
        account_no="123456789012",
        **transport_kwargs,
    )


def _build_request(**overrides) -> KisOrderRequest:
    base = dict(
        symbol="005930",
        side="BUY",
        order_type="LIMIT",
        quantity=10,
        price=70_000,
        account_no="123456789012",
    )
    base.update(overrides)
    return KisOrderRequest(**base)


# ---------------------------------------------------------------------------
# 1. Subclass conformance — HttpxKisOrderTransport implements the ABC
# ---------------------------------------------------------------------------


def test_transport_implements_kis_order_client_interface() -> None:
    transport = _build_transport(
        mock_transport=httpx.MockTransport(lambda request: httpx.Response(200))
    )
    assert isinstance(transport, KisOrderClientInterface)


# ---------------------------------------------------------------------------
# 2. AST guards — module imports stay clean
# ---------------------------------------------------------------------------


def test_no_module_level_httpx_import() -> None:
    """``httpx`` must be imported lazily inside ``__init__``, not at module level."""
    src = _module_source()
    tree = ast.parse(src)
    for node in tree.body:  # only top-level
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            names = (
                [alias.name for alias in node.names]
                if isinstance(node, ast.Import)
                else ([node.module] if node.module else [])
            )
            for name in names:
                assert "httpx" not in (name or ""), (
                    "httpx must be imported lazily inside __init__, "
                    "not at module level"
                )


def test_no_requests_import() -> None:
    src = _module_source()
    tree = ast.parse(src)
    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            names = (
                [alias.name for alias in node.names]
                if isinstance(node, ast.Import)
                else ([node.module] if node.module else [])
            )
            for name in names:
                assert "requests" not in (name or ""), (
                    "requests must not be imported"
                )


def test_no_urllib_import() -> None:
    src = _module_source()
    tree = ast.parse(src)
    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            names = (
                [alias.name for alias in node.names]
                if isinstance(node, ast.Import)
                else ([node.module] if node.module else [])
            )
            for name in names:
                assert "urllib" not in (name or ""), (
                    "urllib must not be imported"
                )


def test_no_app_providers_kis_import() -> None:
    src = _module_source()
    tree = ast.parse(src)
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            assert "app.providers.kis" not in node.module, (
                "app.providers.kis must not be imported (read-only data layer "
                "is structurally separate from the order transport)"
            )
            assert "data.collectors.kis" not in node.module, (
                "app.data.collectors.kis_client must not be imported"
            )


# ---------------------------------------------------------------------------
# 3. __repr__ / str / as_dict — credentials must never leak
# ---------------------------------------------------------------------------


def test_repr_does_not_leak_credentials() -> None:
    transport = _build_transport(
        mock_transport=httpx.MockTransport(lambda request: httpx.Response(200))
    )
    text = repr(transport)
    for forbidden in (
        "kis-app-key-XYZ123",
        "kis-app-secret-XYZ123ABCDEF",
        "kis-access-token-XYZ123",
        "123456789012",  # raw account no
    ):
        assert forbidden not in text, (
            f"repr must not leak {forbidden!r} (got {text!r})"
        )


def test_str_does_not_leak_credentials() -> None:
    transport = _build_transport(
        mock_transport=httpx.MockTransport(lambda request: httpx.Response(200))
    )
    text = str(transport)
    for forbidden in (
        "kis-app-key-XYZ123",
        "kis-app-secret-XYZ123ABCDEF",
        "kis-access-token-XYZ123",
        "123456789012",
    ):
        assert forbidden not in text


def test_as_dict_only_returns_safe_metadata() -> None:
    transport = _build_transport(
        mock_transport=httpx.MockTransport(lambda request: httpx.Response(200))
    )
    payload = transport.as_dict()
    assert set(payload.keys()) == {"base_url", "account_no_masked", "user_agent"}
    assert payload["account_no_masked"].startswith("****")
    # Whitelist check: no key contains 'key' or 'secret' or 'token'
    for key in payload.keys():
        for forbidden in ("api_key", "secret", "token"):
            assert forbidden not in key.lower(), (
                f"as_dict must not expose {key} ({forbidden} forbidden)"
            )
    # Value check: forbidden plaintext must not appear in any value
    for value in payload.values():
        text = str(value)
        for forbidden in (
            "kis-app-key-XYZ123",
            "kis-app-secret-XYZ123ABCDEF",
            "kis-access-token-XYZ123",
            "123456789012",
        ):
            assert forbidden not in text


def test_repr_shows_masked_account_no() -> None:
    transport = _build_transport(
        mock_transport=httpx.MockTransport(lambda request: httpx.Response(200))
    )
    text = repr(transport)
    assert "****9012" in text, (
        f"repr should show last 4 of account_no masked, got {text!r}"
    )


# ---------------------------------------------------------------------------
# 4. place_order — outcome classification
# ---------------------------------------------------------------------------


def test_place_order_success_returns_submitted() -> None:
    captured = {"calls": 0}

    def handler(request):
        captured["calls"] += 1
        return httpx.Response(
            200,
            json={
                "rt_cd": "0",
                "msg_cd": "OPSP0000",
                "msg1": "정상처리 되었습니다.",
                "output": {
                    "KRX_FWDG_ORD_ORGNO": "00950",
                    "ODNO": "0000123456",
                    "ORD_TMD": "120000",
                },
            },
        )

    transport = _build_transport(mock_transport=httpx.MockTransport(handler))
    result = transport.place_order(_build_request())

    assert isinstance(result, KisOrderResult)
    assert result.success is True
    assert result.order_no == "0000123456"
    assert result.message.startswith("SUBMITTED")
    assert captured["calls"] == 1, "place_order must not retry on success"


def test_place_order_business_error_returns_rejected() -> None:
    captured = {"calls": 0}

    def handler(request):
        captured["calls"] += 1
        return httpx.Response(
            200,
            json={
                "rt_cd": "1",
                "msg_cd": "EGW00123",
                "msg1": "주문 가능 수량을 초과했습니다.",
            },
        )

    transport = _build_transport(mock_transport=httpx.MockTransport(handler))
    result = transport.place_order(_build_request())

    assert result.success is False
    assert result.order_no == ""
    assert result.message.startswith("REJECTED")
    assert captured["calls"] == 1, "REJECTED is definitive — no retry"


def test_place_order_4xx_is_classified_rejected_not_retried() -> None:
    captured = {"calls": 0}

    def handler(request):
        captured["calls"] += 1
        return httpx.Response(403, text="forbidden")

    transport = _build_transport(mock_transport=httpx.MockTransport(handler))
    result = transport.place_order(_build_request())

    assert result.success is False
    assert result.message.startswith("REJECTED")
    assert "403" in result.message
    assert captured["calls"] == 1


def test_place_order_5xx_is_classified_unknown_not_retried() -> None:
    captured = {"calls": 0}

    def handler(request):
        captured["calls"] += 1
        return httpx.Response(503, text="service unavailable")

    transport = _build_transport(mock_transport=httpx.MockTransport(handler))
    result = transport.place_order(_build_request())

    assert result.success is False
    assert result.message.startswith("UNKNOWN")
    assert "503" in result.message
    assert captured["calls"] == 1


def test_place_order_timeout_does_not_retry() -> None:
    """The CRITICAL safety property — a place_order that timed out must
    NOT be re-issued because the prior request may have already been
    accepted by KIS."""
    captured = {"calls": 0}

    def handler(request):
        captured["calls"] += 1
        raise httpx.ConnectTimeout("fake timeout", request=request)

    transport = _build_transport(mock_transport=httpx.MockTransport(handler))
    result = transport.place_order(_build_request())

    assert result.success is False
    assert result.message.startswith("TIMEOUT")
    assert captured["calls"] == 1, (
        "place_order MUST be issued exactly once even on timeout — "
        "duplicate-order risk is too high to retry"
    )


def test_place_order_network_error_does_not_retry() -> None:
    captured = {"calls": 0}

    def handler(request):
        captured["calls"] += 1
        raise httpx.ConnectError("refused", request=request)

    transport = _build_transport(mock_transport=httpx.MockTransport(handler))
    result = transport.place_order(_build_request())

    assert result.success is False
    assert result.message.startswith("NETWORK_ERROR")
    assert captured["calls"] == 1


def test_place_order_invalid_json_is_unknown() -> None:
    def handler(request):
        return httpx.Response(200, text="not-json")

    transport = _build_transport(mock_transport=httpx.MockTransport(handler))
    result = transport.place_order(_build_request())

    assert result.success is False
    assert result.message.startswith("UNKNOWN")


def test_place_order_sell_uses_sell_tr_id() -> None:
    captured = {"tr_ids": []}

    def handler(request):
        captured["tr_ids"].append(request.headers.get("tr_id", ""))
        return httpx.Response(
            200,
            json={
                "rt_cd": "0",
                "msg1": "ok",
                "output": {"ODNO": "1111111111"},
            },
        )

    transport = _build_transport(mock_transport=httpx.MockTransport(handler))
    transport.place_order(_build_request(side="SELL"))

    assert captured["tr_ids"][0] != "", "tr_id header must be set"
    # We asserted only that BUY and SELL produce different TR_IDs without
    # binding to the specific values (KIS may publish revised TR_IDs).
    transport.place_order(_build_request(side="BUY"))
    assert captured["tr_ids"][0] != captured["tr_ids"][1], (
        "BUY and SELL must use different TR_IDs"
    )


# ---------------------------------------------------------------------------
# 5. query_fill_status — outcome classification + retry
# ---------------------------------------------------------------------------


def _query_response(*, ord_qty: int, filled: int, cncl="N", rjct="N", rt_cd="0"):
    return httpx.Response(
        200,
        json={
            "rt_cd": rt_cd,
            "msg1": "정상" if rt_cd == "0" else "오류",
            "output1": [
                {
                    "ord_qty": str(ord_qty),
                    "tot_ccld_qty": str(filled),
                    "cncl_yn": cncl,
                    "rjct_yn": rjct,
                }
            ],
        },
    )


def test_query_fill_status_full() -> None:
    def handler(request):
        return _query_response(ord_qty=10, filled=10)

    transport = _build_transport(mock_transport=httpx.MockTransport(handler))
    result = transport.query_fill_status("0000123456")

    assert isinstance(result, KisFillStatusResult)
    assert result.success is True
    assert result.status == "FILLED"
    assert result.filled_quantity == 10
    assert result.remaining_quantity == 0
    assert result.message.startswith("FULL")


def test_query_fill_status_partial() -> None:
    def handler(request):
        return _query_response(ord_qty=10, filled=4)

    transport = _build_transport(mock_transport=httpx.MockTransport(handler))
    result = transport.query_fill_status("0000123456")

    assert result.success is True
    assert result.status == "PARTIALLY_FILLED"
    assert result.filled_quantity == 4
    assert result.remaining_quantity == 6
    assert result.message.startswith("PARTIAL")


def test_query_fill_status_none() -> None:
    def handler(request):
        return _query_response(ord_qty=10, filled=0)

    transport = _build_transport(mock_transport=httpx.MockTransport(handler))
    result = transport.query_fill_status("0000123456")

    assert result.success is True
    assert result.status == "PENDING"
    assert result.filled_quantity == 0
    assert result.remaining_quantity == 10
    assert result.message.startswith("NONE")


def test_query_fill_status_canceled() -> None:
    def handler(request):
        return _query_response(ord_qty=10, filled=0, cncl="Y")

    transport = _build_transport(mock_transport=httpx.MockTransport(handler))
    result = transport.query_fill_status("0000123456")

    assert result.success is False
    assert result.status == "CANCELED"
    assert result.message.startswith("CANCELED")


def test_query_fill_status_rejected() -> None:
    def handler(request):
        return _query_response(ord_qty=10, filled=0, rjct="Y")

    transport = _build_transport(mock_transport=httpx.MockTransport(handler))
    result = transport.query_fill_status("0000123456")

    assert result.success is False
    assert result.status == "REJECTED"
    assert result.message.startswith("REJECTED")


def test_query_fill_status_no_output_returns_none() -> None:
    def handler(request):
        return httpx.Response(
            200, json={"rt_cd": "0", "msg1": "조회결과 없음", "output1": []}
        )

    transport = _build_transport(mock_transport=httpx.MockTransport(handler))
    result = transport.query_fill_status("0000123456")

    assert result.success is True
    assert result.status == "PENDING"
    assert result.message.startswith("NONE")


def test_query_fill_status_business_error_unknown() -> None:
    def handler(request):
        return _query_response(ord_qty=10, filled=0, rt_cd="1")

    transport = _build_transport(mock_transport=httpx.MockTransport(handler))
    result = transport.query_fill_status("0000123456")

    assert result.success is False
    assert result.status == "PENDING"  # UNKNOWN maps to PENDING
    assert result.message.startswith("UNKNOWN")


def test_query_fill_status_retry_succeeds_on_third_attempt() -> None:
    """First 2 attempts time out; 3rd (last allowed) succeeds."""
    captured = {"calls": 0}

    def handler(request):
        captured["calls"] += 1
        if captured["calls"] <= 2:
            raise httpx.ReadTimeout("flaky", request=request)
        return _query_response(ord_qty=10, filled=10)

    transport = _build_transport(mock_transport=httpx.MockTransport(handler))
    result = transport.query_fill_status("0000123456")

    assert captured["calls"] == 3
    assert result.success is True
    assert result.status == "FILLED"


def test_query_fill_status_retry_exhausted_returns_unknown() -> None:
    """All attempts time out — exactly 3 calls (1 + max 2 retries)."""
    captured = {"calls": 0}

    def handler(request):
        captured["calls"] += 1
        raise httpx.ReadTimeout("permanent", request=request)

    transport = _build_transport(mock_transport=httpx.MockTransport(handler))
    result = transport.query_fill_status("0000123456")

    assert captured["calls"] == 3, "max attempts = 1 + 2 retries"
    assert result.success is False
    assert "TIMEOUT" in result.message


def test_query_fill_status_does_not_retry_on_4xx() -> None:
    captured = {"calls": 0}

    def handler(request):
        captured["calls"] += 1
        return httpx.Response(403)

    transport = _build_transport(mock_transport=httpx.MockTransport(handler))
    transport.query_fill_status("0000123456")

    assert captured["calls"] == 1, "HTTP 4xx must not be retried"


def test_query_fill_status_network_error_retries() -> None:
    captured = {"calls": 0}

    def handler(request):
        captured["calls"] += 1
        raise httpx.ConnectError("refused", request=request)

    transport = _build_transport(mock_transport=httpx.MockTransport(handler))
    transport.query_fill_status("0000123456")

    assert captured["calls"] == 3, "network error must retry up to max"


# ---------------------------------------------------------------------------
# 6. cancel_order — outcome classification + retry
# ---------------------------------------------------------------------------


def test_cancel_order_success() -> None:
    def handler(request):
        return httpx.Response(
            200, json={"rt_cd": "0", "msg1": "취소 정상처리"}
        )

    transport = _build_transport(mock_transport=httpx.MockTransport(handler))
    result = transport.cancel_order("0000123456")

    assert isinstance(result, KisCancelResult)
    assert result.success is True
    assert result.order_no == "0000123456"
    assert result.message.startswith("CANCELED")


def test_cancel_order_business_rejected() -> None:
    def handler(request):
        return httpx.Response(
            200, json={"rt_cd": "1", "msg1": "이미 취소된 주문"}
        )

    transport = _build_transport(mock_transport=httpx.MockTransport(handler))
    result = transport.cancel_order("0000123456")

    assert result.success is False
    assert result.message.startswith("REJECTED")


def test_cancel_order_4xx_rejected() -> None:
    def handler(request):
        return httpx.Response(404)

    transport = _build_transport(mock_transport=httpx.MockTransport(handler))
    result = transport.cancel_order("0000123456")

    assert result.success is False
    assert result.message.startswith("REJECTED")
    assert "404" in result.message


def test_cancel_order_5xx_unknown() -> None:
    def handler(request):
        return httpx.Response(502)

    transport = _build_transport(mock_transport=httpx.MockTransport(handler))
    result = transport.cancel_order("0000123456")

    assert result.success is False
    assert result.message.startswith("UNKNOWN")


def test_cancel_order_timeout() -> None:
    captured = {"calls": 0}

    def handler(request):
        captured["calls"] += 1
        raise httpx.ConnectTimeout("timeout", request=request)

    transport = _build_transport(mock_transport=httpx.MockTransport(handler))
    result = transport.cancel_order("0000123456")

    assert captured["calls"] == 3, "cancel must retry up to max (1 + 2)"
    assert result.success is False
    assert result.message.startswith("TIMEOUT")


def test_cancel_order_network_error_retries() -> None:
    captured = {"calls": 0}

    def handler(request):
        captured["calls"] += 1
        raise httpx.ConnectError("refused", request=request)

    transport = _build_transport(mock_transport=httpx.MockTransport(handler))
    transport.cancel_order("0000123456")

    assert captured["calls"] == 3


def test_cancel_order_retry_succeeds_on_second_attempt() -> None:
    captured = {"calls": 0}

    def handler(request):
        captured["calls"] += 1
        if captured["calls"] == 1:
            raise httpx.ReadTimeout("flaky", request=request)
        return httpx.Response(200, json={"rt_cd": "0", "msg1": "ok"})

    transport = _build_transport(mock_transport=httpx.MockTransport(handler))
    result = transport.cancel_order("0000123456")

    assert captured["calls"] == 2
    assert result.success is True


# ---------------------------------------------------------------------------
# 7. Raw response is never returned
# ---------------------------------------------------------------------------


def test_raw_response_fields_are_not_exposed() -> None:
    """Even when KIS returns extra fields, the result dataclass surfaces
    only whitelisted attributes — never the raw response dict."""
    secret_marker = "raw-secret-this-must-not-leak-99999"

    def handler(request):
        return httpx.Response(
            200,
            json={
                "rt_cd": "0",
                "msg1": "ok",
                "output": {
                    "ODNO": "0000123456",
                    "raw_secret_field": secret_marker,
                    "extra": secret_marker + "-extra",
                },
                "extra_top_level": secret_marker + "-top",
            },
        )

    transport = _build_transport(mock_transport=httpx.MockTransport(handler))
    result = transport.place_order(_build_request())

    text = repr(result) + " " + str(result.as_dict())
    assert secret_marker not in text, (
        "Raw response fields must never appear in result repr / as_dict"
    )

    # Result has only the documented attributes — verified by __slots__
    assert set(KisOrderResult.__slots__) == {"success", "order_no", "message"}


def test_query_fill_status_raw_fields_not_exposed() -> None:
    secret_marker = "fill-raw-secret-99999"

    def handler(request):
        return httpx.Response(
            200,
            json={
                "rt_cd": "0",
                "msg1": "ok",
                "output1": [
                    {
                        "ord_qty": "10",
                        "tot_ccld_qty": "10",
                        "cncl_yn": "N",
                        "rjct_yn": "N",
                        "raw_secret_payload": secret_marker,
                        "internal_kis_field": secret_marker + "-2",
                    }
                ],
                "secret_top": secret_marker + "-top",
            },
        )

    transport = _build_transport(mock_transport=httpx.MockTransport(handler))
    result = transport.query_fill_status("0000123456")

    text = repr(result) + " " + str(result.as_dict())
    assert secret_marker not in text


# ---------------------------------------------------------------------------
# 8. Headers / payload — sensitive values masked in logs
# ---------------------------------------------------------------------------


def test_outbound_headers_carry_credentials_to_server_only(caplog) -> None:
    """Credentials MUST flow to the KIS server in headers, but MUST NOT
    appear in any captured log line."""
    captured_headers = {}

    def handler(request):
        # Simulate KIS receiving the headers — record them then respond.
        captured_headers.update(dict(request.headers))
        return httpx.Response(
            200, json={"rt_cd": "0", "msg1": "ok", "output": {"ODNO": "0001"}}
        )

    caplog.set_level(logging.DEBUG, logger="app.broker.kis_order_transport_real")
    transport = _build_transport(mock_transport=httpx.MockTransport(handler))
    transport.place_order(_build_request())

    # Server must have received credentials in headers
    assert captured_headers.get("appkey") == "kis-app-key-XYZ123"
    assert captured_headers.get("appsecret") == "kis-app-secret-XYZ123ABCDEF"
    assert "Bearer kis-access-token-XYZ123" in captured_headers.get(
        "authorization", ""
    )

    # ...but NEVER in caplog
    log_text = "\n".join(record.getMessage() for record in caplog.records)
    for forbidden in (
        "kis-app-key-XYZ123",
        "kis-app-secret-XYZ123ABCDEF",
        "kis-access-token-XYZ123",
    ):
        assert forbidden not in log_text, (
            f"Log captured plaintext credential: {forbidden!r}"
        )


def test_account_no_not_in_log_messages(caplog) -> None:
    def handler(request):
        return httpx.Response(
            200, json={"rt_cd": "0", "msg1": "ok", "output": {"ODNO": "0001"}}
        )

    caplog.set_level(logging.DEBUG, logger="app.broker.kis_order_transport_real")
    transport = _build_transport(mock_transport=httpx.MockTransport(handler))
    transport.place_order(_build_request())
    transport.query_fill_status("0000123456")
    transport.cancel_order("0000123456")

    log_text = "\n".join(record.getMessage() for record in caplog.records)
    assert "123456789012" not in log_text, (
        "Plaintext account_no must never appear in log messages"
    )


# ---------------------------------------------------------------------------
# 9. Retry helper — pure unit tests on _run_with_retries
# ---------------------------------------------------------------------------


def test_retry_helper_returns_first_success_without_retry() -> None:
    counter = {"calls": 0}

    def op() -> _RetryAttempt:
        counter["calls"] += 1
        return _RetryAttempt(
            classification="SUBMITTED",
            result="ok",
            should_retry=False,
        )

    outcome = _run_with_retries(op, max_retries=2)
    assert counter["calls"] == 1
    assert outcome.result == "ok"


def test_retry_helper_retries_until_success() -> None:
    counter = {"calls": 0}

    def op() -> _RetryAttempt:
        counter["calls"] += 1
        if counter["calls"] < 3:
            return _RetryAttempt(
                classification="TIMEOUT", result="t", should_retry=True
            )
        return _RetryAttempt(
            classification="SUBMITTED", result="ok", should_retry=False
        )

    outcome = _run_with_retries(op, max_retries=2)
    assert counter["calls"] == 3
    assert outcome.result == "ok"


def test_retry_helper_caps_at_max_retries() -> None:
    counter = {"calls": 0}

    def op() -> _RetryAttempt:
        counter["calls"] += 1
        return _RetryAttempt(
            classification="TIMEOUT", result="t", should_retry=True
        )

    outcome = _run_with_retries(op, max_retries=2)
    assert counter["calls"] == 3, "1 initial + 2 retries"
    assert outcome.classification == "TIMEOUT"


def test_retry_helper_zero_retries_no_retry() -> None:
    counter = {"calls": 0}

    def op() -> _RetryAttempt:
        counter["calls"] += 1
        return _RetryAttempt(
            classification="TIMEOUT", result="t", should_retry=True
        )

    outcome = _run_with_retries(op, max_retries=0)
    assert counter["calls"] == 1, "0 retries means 1 call total"


# ---------------------------------------------------------------------------
# 10. respx-based integration smoke (no real network — verifies that
#     respx + transport plays nicely together)
# ---------------------------------------------------------------------------


@respx.mock(base_url=_TEST_BASE)
def test_respx_route_is_called(respx_mock) -> None:
    route = respx_mock.post("/uapi/domestic-stock/v1/trading/order-cash").respond(
        200,
        json={"rt_cd": "0", "msg1": "ok", "output": {"ODNO": "respx-987"}},
    )

    s = _settings_for_test()
    transport = HttpxKisOrderTransport(
        settings=s,
        client=httpx.Client(base_url=s.kis_order_base_url),
        app_key="k",
        app_secret="s",
        access_token="t",
        account_no="9999",
    )
    result = transport.place_order(_build_request())

    assert route.called
    assert result.success is True
    assert result.order_no == "respx-987"


# ---------------------------------------------------------------------------
# 11. Settings boundary — timeouts must be positive
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "field",
    [
        "kis_order_place_timeout_s",
        "kis_order_query_timeout_s",
        "kis_order_cancel_timeout_s",
    ],
)
def test_settings_rejects_zero_or_negative_timeout(field: str) -> None:
    kwargs = {field: 0.0}
    with pytest.raises(ValueError):
        Settings(**kwargs)
    kwargs = {field: -1.0}
    with pytest.raises(ValueError):
        Settings(**kwargs)


def test_settings_default_timeouts() -> None:
    """Defaults match the v1.0 Phase B documented values (5/10/5)."""
    import os

    for env in (
        "KIS_ORDER_PLACE_TIMEOUT_S",
        "KIS_ORDER_QUERY_TIMEOUT_S",
        "KIS_ORDER_CANCEL_TIMEOUT_S",
    ):
        os.environ.pop(env, None)
    s = Settings()
    assert s.kis_order_place_timeout_s == 5.0
    assert s.kis_order_query_timeout_s == 10.0
    assert s.kis_order_cancel_timeout_s == 5.0


# ---------------------------------------------------------------------------
# 12. broker __init__.py re-exports
# ---------------------------------------------------------------------------


def test_broker_init_exports_real_transport_symbols() -> None:
    from app.broker import (  # noqa: F401
        CancelClassification,
        FillClassification,
        HttpxKisOrderTransport,
        PlaceClassification,
    )


# ---------------------------------------------------------------------------
# 13. Phase C / Phase D scope guard — Phase B must not pre-empt later phases
# ---------------------------------------------------------------------------


def test_phase_b_does_not_introduce_executor_real_path() -> None:
    """Phase B adds the transport but does NOT wire it into the executor.
    The dry-run executor must still be the only execution path."""
    import importlib

    module = importlib.import_module("app.broker.real_order_executor")
    forbidden = ("execute_real", "real_path_execute", "execute_with_real_transport")
    for name in forbidden:
        assert not hasattr(module, name), (
            f"Phase B must not introduce {name} on the executor — that is Phase C scope"
        )


def test_phase_b_does_not_introduce_real_fill_sync_route() -> None:
    """Phase D scope: POST /api/real-orders/{id}/sync route + real fill sync.
    Phase B must not preempt it."""
    import importlib

    module = importlib.import_module("app.broker.fill_sync_service")
    forbidden = ("sync_fills_real",)
    for name in forbidden:
        assert not hasattr(module, name), (
            f"Phase B must not introduce {name} on FillSyncService — that is Phase D scope"
        )


# ---------------------------------------------------------------------------
# 14. close() lifecycle (best-effort, no exception)
# ---------------------------------------------------------------------------


def test_close_does_not_raise_on_normal_client() -> None:
    transport = _build_transport(
        mock_transport=httpx.MockTransport(lambda request: httpx.Response(200))
    )
    transport.close()  # should not raise


def test_close_swallows_exception_from_buggy_client() -> None:
    s = _settings_for_test()

    class BoomClient:
        def close(self):
            raise RuntimeError("simulated close failure")

    transport = HttpxKisOrderTransport(
        settings=s,
        client=BoomClient(),
        app_key="k",
        app_secret="s",
        access_token="t",
        account_no="9999",
    )
    # close is best-effort — must NOT propagate the exception
    transport.close()
