"""Backtest layer (v0.7 Phase B).

The BacktestEngine joins past Recommendation rows + their RecommendationResult
horizon returns with a Strategy's BUY/PASS/AVOID signals to compute win rate /
average return / max drawdown. It never places orders, never calls a broker,
and never fetches live market data.

Cost adjustment (slippage / fees / tax) and market-regime breakdown land in
Phase C — they are intentionally absent here so Phase B stays a thin
strategy-vs-history evaluator.
"""

from app.backtest.engine import (
    BacktestEngine,
    BacktestRunSummary,
    BUY_ONLY_METRICS_NOTE,
)

__all__ = [
    "BUY_ONLY_METRICS_NOTE",
    "BacktestEngine",
    "BacktestRunSummary",
]
