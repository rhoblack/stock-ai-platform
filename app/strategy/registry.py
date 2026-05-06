"""Name → strategy lookup for v0.7 Phase B CLI / engine.

The registry is the single source of truth for which strategies are *eligible*
for a backtest run. Adding a new strategy requires:

1. Implementing :class:`~app.strategy.interfaces.StrategyInterface` somewhere
   under :mod:`app.strategy`.
2. Registering its constructor in :data:`STRATEGY_REGISTRY` below.
3. Adding the new key to the CLI ``--strategy`` choice list (``KNOWN_STRATEGIES``).

This intentionally does NOT auto-discover via reflection — explicit registry
keeps the supported surface area small and reviewable.
"""

from __future__ import annotations

from collections.abc import Callable

from app.strategy.interfaces import StrategyInterface
from app.strategy.rule_based import (
    HighScoreStrategy,
    MultiSignalStrategy,
    TopGradeStrategy,
)


STRATEGY_REGISTRY: dict[str, Callable[[], StrategyInterface]] = {
    "top_grade": TopGradeStrategy,
    "high_score": HighScoreStrategy,
    "multi_signal": MultiSignalStrategy,
}

KNOWN_STRATEGIES: tuple[str, ...] = tuple(sorted(STRATEGY_REGISTRY))


class UnknownStrategyError(KeyError):
    """Raised when a CLI / engine caller asks for a strategy not in the registry."""


def get_strategy(name: str) -> StrategyInterface:
    """Look up a strategy by short name (e.g. ``"top_grade"``).

    Raises :class:`UnknownStrategyError` (a ``KeyError`` subclass) when the
    name is not registered. The error message lists the known names so the
    caller can surface it to the operator.
    """

    try:
        constructor = STRATEGY_REGISTRY[name]
    except KeyError as exc:
        raise UnknownStrategyError(
            f"unknown strategy {name!r}; expected one of {list(KNOWN_STRATEGIES)}",
        ) from exc
    return constructor()


__all__ = [
    "KNOWN_STRATEGIES",
    "STRATEGY_REGISTRY",
    "UnknownStrategyError",
    "get_strategy",
]
