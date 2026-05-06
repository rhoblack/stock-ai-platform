"""Strategy interface + DTOs for v0.7 Phase A.

* :class:`StrategySignal` — analytical BUY/PASS/AVOID signal with a confidence
  in [0, 1]. **NOT an order**. The system never wires a Strategy output to a
  broker — the only consumer is the (Phase B) BacktestEngine.
* :class:`ScoreSnapshot` — normalized read-model of a Recommendation /
  HoldingCheck row + its v0.5/v0.6 evidence dicts. All fields are optional so
  a strategy can be evaluated against partial data without raising.
* :class:`StrategyInterface` — abstract base. Pure-function ``evaluate`` only;
  no DB / network / Telegram / order side-effects.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any


STRATEGY_ACTION_BUY = "BUY"
STRATEGY_ACTION_PASS = "PASS"
STRATEGY_ACTION_AVOID = "AVOID"

STRATEGY_ACTIONS = frozenset(
    {STRATEGY_ACTION_BUY, STRATEGY_ACTION_PASS, STRATEGY_ACTION_AVOID},
)

_CONFIDENCE_MIN = Decimal("0")
_CONFIDENCE_MAX = Decimal("1")


def _clamp_confidence(value: Decimal) -> Decimal:
    if value < _CONFIDENCE_MIN:
        return _CONFIDENCE_MIN
    if value > _CONFIDENCE_MAX:
        return _CONFIDENCE_MAX
    return value


@dataclass(frozen=True)
class StrategySignal:
    """Analytical signal emitted by a :class:`StrategyInterface`.

    This is *not* an order. It carries no quantity, no price, no account, no
    broker reference. It exists only so the BacktestEngine (Phase B) can pair
    it with ``recommendation_results`` rows and compute win rate / avg return.

    ``action`` is restricted to :data:`STRATEGY_ACTIONS`; any other value
    raises :class:`ValueError` from ``__post_init__``. ``confidence`` is
    automatically clamped into ``[0, 1]`` so callers do not need defensive
    bounds checking.
    """

    action: str
    confidence: Decimal = Decimal("0.5")
    reason: str = ""
    evidence: dict[str, Any] | None = None

    def __post_init__(self) -> None:
        if self.action not in STRATEGY_ACTIONS:
            raise ValueError(
                f"invalid action {self.action!r}; expected one of {sorted(STRATEGY_ACTIONS)}",
            )
        confidence = self.confidence
        if not isinstance(confidence, Decimal):
            confidence = Decimal(str(confidence))
        clamped = _clamp_confidence(confidence)
        # frozen dataclass — bypass via object.__setattr__ to land the clamp.
        object.__setattr__(self, "confidence", clamped)


# Field set kept in a frozenset so test guards (and the v0.7+ schema layer)
# can assert "no order-related fields ever leak in".
SCORE_SNAPSHOT_FIELDS = frozenset(
    {
        "symbol",
        "total_score",
        "grade",
        "technical_score",
        "news_score",
        "supply_score",
        "fundamental_score",
        "earnings_score",
        "ai_score",
        "report_score",
        "theme_signal_score",
        "risk_level",
        "risk_flags",
        "evidence",
    },
)


@dataclass(frozen=True)
class ScoreSnapshot:
    """Normalized view of a recommendation / holding-check row for strategies.

    All numeric fields are optional — when a producer was not wired or the
    snapshot pre-dates a v0.5/v0.6 evidence field, the value is ``None`` and
    the strategy is expected to default to PASS (never raise).

    The dataclass intentionally **does not** carry order-side fields
    (quantity, price, account, broker) — see ``test_score_snapshot_does_not_carry_order_fields``.
    """

    symbol: str
    total_score: Decimal | None = None
    grade: str | None = None
    technical_score: Decimal | None = None
    news_score: Decimal | None = None
    supply_score: Decimal | None = None
    fundamental_score: Decimal | None = None
    earnings_score: Decimal | None = None
    ai_score: Decimal | None = None
    report_score: Decimal | None = None
    theme_signal_score: Decimal | None = None
    risk_level: str | None = None
    risk_flags: list[str] = field(default_factory=list)
    evidence: dict[str, Any] | None = None


class StrategyInterface(ABC):
    """Abstract base for analytical strategies (v0.7 Phase A).

    Implementations must be **pure** — no DB queries, no HTTP calls, no
    Telegram, no order placement, no file I/O. Given the same ``snapshot``
    they must always return the same :class:`StrategySignal`. This guarantee
    is what lets the BacktestEngine (Phase B) replay snapshots deterministically.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        raise NotImplementedError

    @property
    @abstractmethod
    def version(self) -> str:
        raise NotImplementedError

    @abstractmethod
    def evaluate(self, snapshot: ScoreSnapshot) -> StrategySignal:
        raise NotImplementedError


__all__ = [
    "SCORE_SNAPSHOT_FIELDS",
    "STRATEGY_ACTIONS",
    "STRATEGY_ACTION_AVOID",
    "STRATEGY_ACTION_BUY",
    "STRATEGY_ACTION_PASS",
    "ScoreSnapshot",
    "StrategyInterface",
    "StrategySignal",
]
