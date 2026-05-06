"""Placeholder transaction cost model for v0.7 Phase C BacktestEngine.

This is **not** a real broker fee schedule. The constants are conservative
estimates so that backtest win-rate / avg-return numbers do not over-promise
when traders compare them against live-quoted P&L. Real per-broker fee
schedules, per-symbol stamp duty rates, and per-tick slippage modelling are
v0.8+ work and require their own license / vendor checks.

Values
------
* ``buy_fee``   = 0.015%  (KRX 일반 위탁 수수료 보수치)
* ``sell_fee``  = 0.015%  (동일)
* ``sell_tax``  = 0.20%   (KOSPI 거래세 보수치)
* ``slippage``  = 0.10%   (호가 1틱 가정의 단방향 보수 추정)
* ``total_cost`` = 0.0033 = **0.33%** (네 항목 합)

The engine subtracts ``total_cost`` from each BUY signal's ``return_5d``
exactly once. We do not double-count slippage on the sell side because the
recorded ``recommendation_results.close_return`` already reflects an exit at
the close (no extra slippage assumption).

Out of scope for v0.7
---------------------
* Per-broker fee tier
* Per-symbol stamp duty (KOSDAQ vs KOSPI vs ETF)
* Tick-size aware slippage
* Bid-ask spread modelling
* Borrow / short fees
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal


COST_MODEL_VERSION = "constant-v1"


@dataclass(frozen=True)
class CostModel:
    """Sum-of-constants transaction cost model.

    All fields are :class:`~decimal.Decimal` rates (1.0 == 100%). ``apply``
    subtracts the running ``total_cost`` from a raw return; pass ``None`` to
    propagate a missing-data signal (the engine uses this for horizons that
    had no ``recommendation_results.close_return`` row).
    """

    buy_fee: Decimal = Decimal("0.00015")
    sell_fee: Decimal = Decimal("0.00015")
    sell_tax: Decimal = Decimal("0.0020")
    slippage: Decimal = Decimal("0.0010")
    version: str = COST_MODEL_VERSION

    @property
    def total_cost(self) -> Decimal:
        return self.buy_fee + self.sell_fee + self.sell_tax + self.slippage

    def apply(self, raw_return: Decimal | None) -> Decimal | None:
        """Subtract ``total_cost`` from ``raw_return`` (or return ``None``).

        ``raw_return`` and the resulting cost-adjusted value are expressed in
        the same units as ``recommendation_results.close_return`` — **percent**
        (e.g. ``1.5`` for +1.50%), not fractions. ``total_cost`` is a fraction
        (e.g. ``0.0033`` for 0.33%) so it is multiplied by 100 before
        subtraction.
        """

        if raw_return is None:
            return None
        return raw_return - (self.total_cost * Decimal("100"))


__all__ = ["COST_MODEL_VERSION", "CostModel"]
