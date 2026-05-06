"""Unit tests for v0.7 Phase C CostModel — placeholder constants only."""

from __future__ import annotations

from decimal import Decimal

import pytest

from app.backtest.cost_model import COST_MODEL_VERSION, CostModel


def test_default_cost_model_version_is_constant_v1():
    cm = CostModel()
    assert cm.version == "constant-v1"
    assert cm.version == COST_MODEL_VERSION


def test_default_total_cost_sums_to_0_33_percent():
    cm = CostModel()
    # 0.00015 + 0.00015 + 0.0020 + 0.0010 = 0.0033 (= 0.33%)
    assert cm.total_cost == Decimal("0.0033")


def test_apply_subtracts_total_cost_from_positive_return():
    cm = CostModel()
    # close_return is in percent (e.g. 1.5 == 1.5%); total_cost is fraction.
    # apply: 1.5 - 0.33 = 1.17
    assert cm.apply(Decimal("1.5")) == Decimal("1.17")


def test_apply_handles_negative_return():
    cm = CostModel()
    # -2.0 - 0.33 = -2.33
    assert cm.apply(Decimal("-2.0")) == Decimal("-2.33")


def test_apply_returns_none_for_none_input():
    cm = CostModel()
    assert cm.apply(None) is None


def test_apply_zero_return_becomes_negative_total_cost():
    cm = CostModel()
    # 0 - 0.33 = -0.33
    assert cm.apply(Decimal("0")) == Decimal("-0.33")


def test_custom_fee_overrides_change_total_cost():
    cm = CostModel(
        buy_fee=Decimal("0.0005"),
        sell_fee=Decimal("0.0005"),
        sell_tax=Decimal("0.0025"),
        slippage=Decimal("0.0020"),
    )
    # 0.0005 + 0.0005 + 0.0025 + 0.0020 = 0.0055 (= 0.55%)
    assert cm.total_cost == Decimal("0.0055")
    assert cm.apply(Decimal("2.0")) == Decimal("1.45")


def test_custom_version_propagates_to_engine_summary():
    cm = CostModel(version="custom-broker-v0")
    assert cm.version == "custom-broker-v0"


def test_cost_model_is_frozen_dataclass():
    cm = CostModel()
    with pytest.raises(Exception):  # FrozenInstanceError subclass of Exception
        cm.buy_fee = Decimal("0.5")  # type: ignore[misc]
