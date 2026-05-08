"""Unit tests for v0.16 Phase B — KIS Order Client Interface and FakeKisOrderTransport.

Scope:
  * KisOrderClientInterface ABC cannot be instantiated directly.
  * FakeKisOrderTransport implements the interface without external calls.
  * KisOrderRequest repr / as_dict masks account_no.
  * KisOrderRequest validation rejects bad side / order_type / quantity / price.
  * KisOrderResult, KisFillStatusResult, KisCancelResult as_dict correctness.
  * KisFillStatusResult rejects unknown status strings.
  * mask_sensitive_order_payload masks known sensitive keys (case-insensitive).
  * AST guard: no httpx / requests / urllib imported in kis_order_client.py.
  * AST guard: no app.data.collectors.kis_client imported in kis_order_client.py.
  * FakeKisOrderTransport order_no is deterministic FAKE-XXXXXX pattern.
  * FakeKisOrderTransport.query_fill_status always returns FILLED.
  * FakeKisOrderTransport.cancel_order always returns success=True.
  * Phase B does NOT create RealOrder / RealFill ORM modules (Phase C guard).
  * Phase B does NOT create RealOrderExecutor (Phase D guard).
"""

from __future__ import annotations

import ast
import pathlib

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _module_source() -> str:
    path = pathlib.Path(__file__).resolve().parents[2] / "app" / "broker" / "kis_order_client.py"
    return path.read_text(encoding="utf-8")


def _build_request(**overrides: object) -> "KisOrderRequest":  # type: ignore[name-defined]
    from app.broker.kis_order_client import KisOrderRequest

    defaults = {
        "symbol": "005930",
        "side": "BUY",
        "order_type": "LIMIT",
        "quantity": 10,
        "price": 75_000,
        "account_no": "12345678901",
    }
    defaults.update(overrides)  # type: ignore[arg-type]
    return KisOrderRequest(**defaults)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# 1. ABC — cannot instantiate directly
# ---------------------------------------------------------------------------


def test_kis_order_client_interface_is_abstract() -> None:
    from app.broker.kis_order_client import KisOrderClientInterface

    with pytest.raises(TypeError):
        KisOrderClientInterface()  # type: ignore[abstract]


# ---------------------------------------------------------------------------
# 2. KisOrderRequest — immutability
# ---------------------------------------------------------------------------


def test_kis_order_request_is_immutable() -> None:
    req = _build_request()
    with pytest.raises(AttributeError):
        req.symbol = "000660"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# 3. KisOrderRequest — repr masks account_no
# ---------------------------------------------------------------------------


def test_kis_order_request_repr_masks_account_no() -> None:
    req = _build_request(account_no="12345678901")
    r = repr(req)
    assert "12345678901" not in r
    assert "8901" in r  # last-4 suffix is visible
    assert "****" in r


def test_kis_order_request_as_dict_masks_account_no() -> None:
    req = _build_request(account_no="12345678901")
    d = req.as_dict()
    assert d["account_no"] != "12345678901"
    assert "8901" in d["account_no"]
    assert "****" in d["account_no"]


# ---------------------------------------------------------------------------
# 4. KisOrderRequest — validation
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("bad_side", ["buy", "SELL ", "SHORT", "", "B"])
def test_kis_order_request_rejects_bad_side(bad_side: str) -> None:
    with pytest.raises(ValueError, match="side"):
        _build_request(side=bad_side)


@pytest.mark.parametrize("bad_type", ["limit", "MKT", "STOP", ""])
def test_kis_order_request_rejects_bad_order_type(bad_type: str) -> None:
    with pytest.raises(ValueError, match="order_type"):
        _build_request(order_type=bad_type)


def test_kis_order_request_rejects_zero_quantity() -> None:
    with pytest.raises(ValueError, match="quantity"):
        _build_request(quantity=0)


def test_kis_order_request_rejects_negative_quantity() -> None:
    with pytest.raises(ValueError, match="quantity"):
        _build_request(quantity=-1)


def test_kis_order_request_rejects_negative_price() -> None:
    with pytest.raises(ValueError, match="price"):
        _build_request(price=-1)


def test_kis_order_request_allows_zero_price_for_market() -> None:
    # Market orders legitimately use price=0
    req = _build_request(order_type="MARKET", price=0)
    assert req.price == 0


# ---------------------------------------------------------------------------
# 5. KisFillStatusResult — rejects unknown status
# ---------------------------------------------------------------------------


def test_kis_fill_status_result_rejects_unknown_status() -> None:
    from app.broker.kis_order_client import KisFillStatusResult

    with pytest.raises(ValueError, match="status"):
        KisFillStatusResult(
            success=True,
            order_no="X-001",
            filled_quantity=0,
            remaining_quantity=10,
            status="UNKNOWN_STATUS",
            message="bad",
        )


# ---------------------------------------------------------------------------
# 6. Result dataclasses — as_dict correctness
# ---------------------------------------------------------------------------


def test_kis_order_result_as_dict() -> None:
    from app.broker.kis_order_client import KisOrderResult

    r = KisOrderResult(success=True, order_no="ORD-001", message="ok")
    d = r.as_dict()
    assert d == {"success": True, "order_no": "ORD-001", "message": "ok"}


def test_kis_fill_status_result_as_dict() -> None:
    from app.broker.kis_order_client import KisFillStatusResult

    r = KisFillStatusResult(
        success=True,
        order_no="ORD-002",
        filled_quantity=5,
        remaining_quantity=5,
        status="PARTIALLY_FILLED",
        message="half filled",
    )
    d = r.as_dict()
    assert d["status"] == "PARTIALLY_FILLED"
    assert d["filled_quantity"] == 5
    assert d["remaining_quantity"] == 5


def test_kis_cancel_result_as_dict() -> None:
    from app.broker.kis_order_client import KisCancelResult

    r = KisCancelResult(success=True, order_no="ORD-003", message="canceled")
    d = r.as_dict()
    assert d == {"success": True, "order_no": "ORD-003", "message": "canceled"}


# ---------------------------------------------------------------------------
# 7. FakeKisOrderTransport — place_order
# ---------------------------------------------------------------------------


def test_fake_transport_place_order_succeeds() -> None:
    from app.broker.kis_order_client import FakeKisOrderTransport

    transport = FakeKisOrderTransport()
    req = _build_request()
    result = transport.place_order(req)
    assert result.success is True
    assert result.order_no.startswith("FAKE-")


def test_fake_transport_order_no_is_incrementing() -> None:
    from app.broker.kis_order_client import FakeKisOrderTransport

    transport = FakeKisOrderTransport()
    r1 = transport.place_order(_build_request())
    r2 = transport.place_order(_build_request())
    n1 = int(r1.order_no.split("-")[1])
    n2 = int(r2.order_no.split("-")[1])
    assert n2 == n1 + 1


# ---------------------------------------------------------------------------
# 8. FakeKisOrderTransport — query_fill_status
# ---------------------------------------------------------------------------


def test_fake_transport_query_fill_status_returns_filled() -> None:
    from app.broker.kis_order_client import FakeKisOrderTransport

    transport = FakeKisOrderTransport()
    result = transport.query_fill_status("FAKE-000001")
    assert result.success is True
    assert result.status == "FILLED"


# ---------------------------------------------------------------------------
# 9. FakeKisOrderTransport — cancel_order
# ---------------------------------------------------------------------------


def test_fake_transport_cancel_order_succeeds() -> None:
    from app.broker.kis_order_client import FakeKisOrderTransport

    transport = FakeKisOrderTransport()
    result = transport.cancel_order("FAKE-000001")
    assert result.success is True
    assert result.order_no == "FAKE-000001"


# ---------------------------------------------------------------------------
# 10. mask_sensitive_order_payload
# ---------------------------------------------------------------------------


def test_mask_sensitive_payload_masks_known_keys() -> None:
    from app.broker.kis_order_client import mask_sensitive_order_payload

    payload = {
        "symbol": "005930",
        "api_key": "real-api-key-value",
        "api_secret": "real-secret-value",
        "account_no": "12345678901",
        "quantity": 10,
    }
    masked = mask_sensitive_order_payload(payload)
    assert masked["symbol"] == "005930"
    assert masked["quantity"] == 10
    assert masked["api_key"] == "***MASKED***"
    assert masked["api_secret"] == "***MASKED***"
    assert masked["account_no"] == "***MASKED***"


def test_mask_sensitive_payload_is_case_insensitive() -> None:
    from app.broker.kis_order_client import mask_sensitive_order_payload

    payload = {"API_KEY": "secret", "Authorization": "Bearer token-value"}
    masked = mask_sensitive_order_payload(payload)
    assert masked["API_KEY"] == "***MASKED***"
    assert masked["Authorization"] == "***MASKED***"


def test_mask_sensitive_payload_does_not_mutate_original() -> None:
    from app.broker.kis_order_client import mask_sensitive_order_payload

    original = {"api_key": "secret", "symbol": "005930"}
    mask_sensitive_order_payload(original)
    assert original["api_key"] == "secret"


# ---------------------------------------------------------------------------
# 11. __init__.py re-exports
# ---------------------------------------------------------------------------


def test_broker_init_exports_kis_symbols() -> None:
    from app.broker import (  # noqa: F401
        FakeKisOrderTransport,
        KisCancelResult,
        KisFillStatusResult,
        KisOrderClientInterface,
        KisOrderRequest,
        KisOrderResult,
        mask_sensitive_order_payload,
    )


# ---------------------------------------------------------------------------
# 12. AST guard — no forbidden imports in kis_order_client.py
# ---------------------------------------------------------------------------


def test_kis_order_client_has_no_httpx_import() -> None:
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
                assert "httpx" not in (name or ""), (
                    "httpx must not be imported in kis_order_client.py"
                )


def test_kis_order_client_has_no_requests_import() -> None:
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
                    "requests must not be imported in kis_order_client.py"
                )


def test_kis_order_client_has_no_urllib_import() -> None:
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
                    "urllib must not be imported in kis_order_client.py"
                )


def test_kis_order_client_has_no_data_collectors_kis_import() -> None:
    """kis_order_client.py must not import app.data.collectors.kis_client."""
    src = _module_source()
    tree = ast.parse(src)
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            assert "data.collectors.kis" not in node.module, (
                "app.data.collectors.kis_client must not be imported in kis_order_client.py"
            )


# ---------------------------------------------------------------------------
# 13. Phase C / D guard — future artefacts must not exist yet
# ---------------------------------------------------------------------------


def test_v016_phase_b_real_order_orm_not_yet_created() -> None:
    """Phase B must NOT create RealOrder / RealFill ORM modules (Phase C)."""
    repo_dir = pathlib.Path(__file__).resolve().parents[2] / "app" / "data" / "repositories"
    assert not (repo_dir / "real_order.py").exists(), (
        "real_order.py must not exist in Phase B — it is a Phase C artefact"
    )
    assert not (repo_dir / "real_fill.py").exists(), (
        "real_fill.py must not exist in Phase B — it is a Phase C artefact"
    )


def test_v016_phase_b_real_order_executor_not_yet_created() -> None:
    """Phase B must NOT create RealOrderExecutor (Phase D scope)."""
    broker_dir = pathlib.Path(__file__).resolve().parents[2] / "app" / "broker"
    assert not (broker_dir / "real_order_executor.py").exists(), (
        "real_order_executor.py must not exist in Phase B — it is a Phase D artefact"
    )
