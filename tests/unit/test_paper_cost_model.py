"""Unit tests for v0.14 Phase C ``PaperTradingCostModel``.

Scope:
  * Default rates match the spec (0.015% / 0.015% / 0.18% / 0.05%).
  * Rates are independent from :class:`CostModel` -- the existing backtest
    constants must remain untouched.
  * BUY / SELL paths produce the documented gross / fee / stamp_tax /
    slippage / net amounts.
  * Edge cases: invalid side, zero quantity, zero price.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from app.backtest.cost_model import (
    COST_MODEL_VERSION,
    CostModel,
    PAPER_COST_MODEL_VERSION,
    PaperFillCosts,
    PaperTradingCostModel,
)


def test_paper_model_default_rates_match_spec():
    cm = PaperTradingCostModel()
    assert cm.buy_fee_rate == Decimal("0.00015")
    assert cm.sell_fee_rate == Decimal("0.00015")
    assert cm.sell_tax_rate == Decimal("0.0018")
    assert cm.slippage_rate == Decimal("0.0005")
    assert cm.version == PAPER_COST_MODEL_VERSION == "paper-v1"


def test_backtest_cost_model_constants_unchanged_by_phase_c():
    """Phase C must NOT regress the v0.7 BacktestEngine cost constants."""
    cm = CostModel()
    assert cm.buy_fee == Decimal("0.00015")
    assert cm.sell_fee == Decimal("0.00015")
    assert cm.sell_tax == Decimal("0.0020")
    assert cm.slippage == Decimal("0.0010")
    assert cm.total_cost == Decimal("0.0033")
    assert cm.version == COST_MODEL_VERSION == "constant-v1"


def test_buy_costs_no_stamp_tax_and_net_includes_fee_and_slippage():
    cm = PaperTradingCostModel()
    costs = cm.compute(side="BUY", fill_price=Decimal("10000"), quantity=10)
    # gross = 100,000; fee = 15; slippage = 50; tax = 0; net = 100,065
    assert costs == PaperFillCosts(
        gross_amount=Decimal("100000.0000"),
        fee=Decimal("15.0000"),
        stamp_tax=Decimal("0"),
        slippage=Decimal("50.0000"),
        net_amount=Decimal("100065.0000"),
    )


def test_sell_costs_subtracts_fee_tax_and_slippage_from_gross():
    cm = PaperTradingCostModel()
    costs = cm.compute(side="SELL", fill_price=Decimal("10000"), quantity=10)
    # gross = 100,000; fee = 15; tax = 180; slippage = 50; net = 99,755
    assert costs.gross_amount == Decimal("100000.0000")
    assert costs.fee == Decimal("15.0000")
    assert costs.stamp_tax == Decimal("180.0000")
    assert costs.slippage == Decimal("50.0000")
    assert costs.net_amount == Decimal("99755.0000")


def test_custom_rates_propagate():
    cm = PaperTradingCostModel(
        buy_fee_rate=Decimal("0.001"),
        sell_fee_rate=Decimal("0.001"),
        sell_tax_rate=Decimal("0.005"),
        slippage_rate=Decimal("0.002"),
    )
    buy = cm.compute(side="BUY", fill_price=Decimal("1000"), quantity=1)
    # gross 1000; fee 1; slippage 2; tax 0; net 1003
    assert buy.fee == Decimal("1.0000")
    assert buy.slippage == Decimal("2.0000")
    assert buy.net_amount == Decimal("1003.0000")


@pytest.mark.parametrize(
    "kwargs,match",
    [
        (dict(side="HOLD", fill_price=Decimal("1"), quantity=1), "side must be"),
        (dict(side="BUY", fill_price=Decimal("0"), quantity=1), "fill_price must be > 0"),
        (dict(side="BUY", fill_price=Decimal("1"), quantity=0), "quantity must be > 0"),
        (dict(side="SELL", fill_price=Decimal("-1"), quantity=1), "fill_price must be > 0"),
    ],
)
def test_invalid_input_rejected(kwargs, match):
    cm = PaperTradingCostModel()
    with pytest.raises(ValueError, match=match):
        cm.compute(**kwargs)


def test_paper_cost_model_is_frozen():
    cm = PaperTradingCostModel()
    with pytest.raises(Exception):  # FrozenInstanceError subclasses Exception
        cm.buy_fee_rate = Decimal("0.5")  # type: ignore[misc]
