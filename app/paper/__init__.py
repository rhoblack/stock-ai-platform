"""v0.14 Phase C -- Paper / Simulation Trading PnL & Fill Engine.

This subpackage owns the in-process bookkeeping that turns a CREATED
``VirtualOrder`` into a ``VirtualFill`` plus the resulting ``VirtualPosition``
update and (optional) daily ``VirtualPnLSnapshot``. None of the modules in
here import KIS / DART / RSS / requests / httpx; the engine is pure local
state mutation backed by ``daily_prices.close``.
"""

from app.paper.pnl_tracker import (
    FillResult,
    InsufficientCashError,
    PnLTracker,
)


__all__ = [
    "FillResult",
    "InsufficientCashError",
    "PnLTracker",
]
