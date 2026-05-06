"""Strategy layer (v0.7 Phase A).

Strategies are *pure analytical signal producers*. They consume a normalized
``ScoreSnapshot`` (built from a recommendation row + its evidence dicts) and
emit a ``StrategySignal`` (BUY / PASS / AVOID + confidence + reason). They do
not place orders, do not call external APIs, do not write to the database.

This package is the entry point for v0.7's "is this recommendation actually
profitable?" question — strategies feed the v0.7 Phase B BacktestEngine, which
joins them with ``recommendation_results`` (1/3/5/20-day returns) to compute
win rate / avg return / max drawdown.

Anything that talks to a broker, places an order, or fetches live market data
is explicitly out of scope here and forbidden by AGENTS.md.
"""

from app.strategy.interfaces import (
    SCORE_SNAPSHOT_FIELDS,
    STRATEGY_ACTIONS,
    STRATEGY_ACTION_AVOID,
    STRATEGY_ACTION_BUY,
    STRATEGY_ACTION_PASS,
    ScoreSnapshot,
    StrategyInterface,
    StrategySignal,
)
from app.strategy.rule_based import (
    HighScoreStrategy,
    MultiSignalStrategy,
    TopGradeStrategy,
)

__all__ = [
    "HighScoreStrategy",
    "MultiSignalStrategy",
    "SCORE_SNAPSHOT_FIELDS",
    "STRATEGY_ACTIONS",
    "STRATEGY_ACTION_AVOID",
    "STRATEGY_ACTION_BUY",
    "STRATEGY_ACTION_PASS",
    "ScoreSnapshot",
    "StrategyInterface",
    "StrategySignal",
    "TopGradeStrategy",
]
