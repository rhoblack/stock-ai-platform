"""Sector breakdown helper for v0.12 Phase C MultiStrategyRunner.

Provides ``SectorBreakdownEntry`` and ``aggregate_sector_breakdown()``, a pure
aggregation function that takes a flat list of (sector, action, return_5d)
triples and returns per-sector BUY metrics.

Design notes
------------
* ``None`` sector → :data:`UNKNOWN_SECTOR_BUCKET` ("UNKNOWN") so callers never
  need to guard for None in the output list.
* Only BUY signals contribute to ``win_rate_5d`` / ``avg_return_5d`` — identical
  policy to :mod:`app.backtest.engine`.
* Entries are sorted by ``buy_count desc``, then ``sector`` asc for
  deterministic output regardless of insertion order.
* No DB access — the caller is responsible for fetching sector data and
  horizon returns before calling this function.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from app.strategy.interfaces import STRATEGY_ACTION_BUY


UNKNOWN_SECTOR_BUCKET = "UNKNOWN"


@dataclass(frozen=True)
class SectorBreakdownEntry:
    """Per-sector BUY metrics for a single strategy evaluation pass."""

    sector: str
    signal_count: int
    buy_count: int
    win_rate_5d: Decimal | None
    avg_return_5d: Decimal | None

    def as_dict(self) -> dict[str, Any]:
        return {
            "sector": self.sector,
            "signal_count": self.signal_count,
            "buy_count": self.buy_count,
            "win_rate_5d": _dstr(self.win_rate_5d),
            "avg_return_5d": _dstr(self.avg_return_5d),
        }


def aggregate_sector_breakdown(
    triples: list[tuple[str | None, str, Decimal | None]],
) -> list[SectorBreakdownEntry]:
    """Aggregate ``(sector, action, return_5d)`` triples into per-sector entries.

    Args:
        triples: Each element is ``(sector_or_None, signal_action, return_5d_or_None)``.
            ``None`` sector folds into :data:`UNKNOWN_SECTOR_BUCKET`.

    Returns:
        Sorted list of :class:`SectorBreakdownEntry` — ``buy_count desc``, then
        ``sector`` asc for determinism.  Empty input → empty list.
    """

    by_sector: dict[str, list[tuple[str, Decimal | None]]] = {}
    for sector, action, return_5d in triples:
        bucket = sector if sector else UNKNOWN_SECTOR_BUCKET
        by_sector.setdefault(bucket, []).append((action, return_5d))

    entries: list[SectorBreakdownEntry] = []
    for sector_name, signals in by_sector.items():
        signal_count = len(signals)
        buy_returns = [r for a, r in signals if a == STRATEGY_ACTION_BUY and r is not None]
        buy_count = sum(1 for a, _ in signals if a == STRATEGY_ACTION_BUY)

        if buy_returns:
            wins = sum(1 for v in buy_returns if v > 0)
            win_rate_5d = (Decimal(wins) / Decimal(len(buy_returns))).quantize(Decimal("0.0001"))
            avg_return_5d = (sum(buy_returns) / Decimal(len(buy_returns))).quantize(Decimal("0.0001"))
        else:
            win_rate_5d = None
            avg_return_5d = None

        entries.append(
            SectorBreakdownEntry(
                sector=sector_name,
                signal_count=signal_count,
                buy_count=buy_count,
                win_rate_5d=win_rate_5d,
                avg_return_5d=avg_return_5d,
            )
        )

    entries.sort(key=lambda e: (-e.buy_count, e.sector))
    return entries


def _dstr(v: Decimal | None) -> str | None:
    return str(v) if v is not None else None


__all__ = [
    "UNKNOWN_SECTOR_BUCKET",
    "SectorBreakdownEntry",
    "aggregate_sector_breakdown",
]
