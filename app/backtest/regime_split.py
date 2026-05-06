"""Market-regime assignment helper for v0.7 Phase C BacktestEngine.

Given a signal date and a market code, look up the most recent
``MarketRegime`` row at-or-before that date and return its ``regime`` string
(e.g. ``"UPTREND_EARLY"``). If no row exists for the market on or before
``signal_date`` the function returns ``None`` — the engine then buckets the
signal under :data:`UNCLASSIFIED_BUCKET` in its summary breakdown.

This helper does **not** call any external API. It only reads from the
existing ``market_regimes`` table (populated by the v0.3 jobs).
"""

from __future__ import annotations

from datetime import date

from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.db.models import MarketRegime


UNCLASSIFIED_BUCKET = "UNCLASSIFIED"
DEFAULT_MARKET = "KOSPI"


def assign_regime(
    session: Session,
    signal_date: date,
    *,
    market: str = DEFAULT_MARKET,
) -> str | None:
    """Return the regime string at-or-before ``signal_date`` for ``market``.

    Strategy: pick the **most recent** ``market_regimes`` row whose
    ``date <= signal_date`` and ``market == market``. If none exist (e.g. the
    signal date precedes the first regime ingest) → ``None``.

    The engine wraps a ``None`` result with :data:`UNCLASSIFIED_BUCKET` for
    summary display, but the persisted ``BacktestResult.regime`` column stays
    ``NULL`` so future re-runs (after late regime data lands) can re-assign
    cleanly.
    """

    statement = (
        select(MarketRegime.regime)
        .where(
            MarketRegime.market == market,
            MarketRegime.date <= signal_date,
        )
        .order_by(desc(MarketRegime.date))
        .limit(1)
    )
    row = session.execute(statement).first()
    return row[0] if row is not None else None


def display_bucket(regime: str | None) -> str:
    """Map ``None`` → ``UNCLASSIFIED`` for summary breakdown / UI."""

    return regime if regime else UNCLASSIFIED_BUCKET


__all__ = [
    "DEFAULT_MARKET",
    "UNCLASSIFIED_BUCKET",
    "assign_regime",
    "display_bucket",
]
