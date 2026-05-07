"""MultiStrategyRunner — v0.12 Phase C.

Runs multiple :class:`~app.strategy.interfaces.StrategyInterface` instances
over the **same** date range and universe, then produces a ranked comparison
table.  Per-strategy regime breakdown reuses the already-computed data from
:class:`~app.backtest.engine.BacktestEngine`; sector breakdown is computed
via a separate bulk query against the ``stocks`` table so no new DB columns
are required.

All results are persisted (when ``dry_run=False``) in **one** ``BacktestRun``
row whose ``summary_json["multi_strategy_comparison"]`` key holds the full
comparison detail.  The walk-forward ``summary_json["walk_forward_folds"]``
key used by Phase B is unaffected.

Side-effect policy
------------------
* Per-strategy :class:`~app.backtest.engine.BacktestEngine` runs are always
  ``dry_run=True`` — no per-strategy DB rows.
* ``dry_run=True`` (default): no ``BacktestRun`` row created at any level.
* ``dry_run=False``: exactly **one** ``BacktestRun`` row with
  ``strategy_name="MULTI"`` and ``summary_json`` containing full comparison.
* No external HTTP / KIS / DART / Telegram calls. No Alembic revisions.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import Any

from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.backtest.cost_model import CostModel
from app.backtest.engine import (
    BUY_ONLY_METRICS_NOTE,
    BacktestEngine,
    RegimeBreakdownEntry,
    build_score_snapshot,
)
from app.backtest.regime_breakdown import SectorBreakdownEntry, aggregate_sector_breakdown
from app.backtest.regime_split import DEFAULT_MARKET
from app.data.repositories.backtest_runs import BacktestRunRepository, STATUS_DRY_RUN
from app.db.models import (
    DataSnapshot,
    Recommendation,
    RecommendationResult,
    RecommendationRun,
    Stock,
)
from app.strategy.interfaces import StrategyInterface


# ---------------------------------------------------------------------------
# Result types
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class StrategyResult:
    """Per-strategy metrics row in a :class:`MultiStrategyComparison`."""

    strategy_name: str
    strategy_version: str
    signal_count: int
    buy_count: int
    pass_count: int
    avoid_count: int
    win_rate_1d: Decimal | None
    win_rate_3d: Decimal | None
    win_rate_5d: Decimal | None
    win_rate_20d: Decimal | None
    avg_return_1d: Decimal | None
    avg_return_3d: Decimal | None
    avg_return_5d: Decimal | None
    avg_return_20d: Decimal | None
    cost_adjusted_avg_return_5d: Decimal | None
    max_drawdown: Decimal | None
    regime_breakdown: list[RegimeBreakdownEntry] = field(default_factory=list)
    sector_breakdown: list[SectorBreakdownEntry] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "strategy_name": self.strategy_name,
            "strategy_version": self.strategy_version,
            "signal_count": self.signal_count,
            "buy_count": self.buy_count,
            "pass_count": self.pass_count,
            "avoid_count": self.avoid_count,
            "win_rate_1d": _dstr(self.win_rate_1d),
            "win_rate_3d": _dstr(self.win_rate_3d),
            "win_rate_5d": _dstr(self.win_rate_5d),
            "win_rate_20d": _dstr(self.win_rate_20d),
            "avg_return_1d": _dstr(self.avg_return_1d),
            "avg_return_3d": _dstr(self.avg_return_3d),
            "avg_return_5d": _dstr(self.avg_return_5d),
            "avg_return_20d": _dstr(self.avg_return_20d),
            "cost_adjusted_avg_return_5d": _dstr(self.cost_adjusted_avg_return_5d),
            "max_drawdown": _dstr(self.max_drawdown),
            "regime_breakdown": [e.as_dict() for e in self.regime_breakdown],
            "sector_breakdown": [e.as_dict() for e in self.sector_breakdown],
        }


@dataclass(frozen=True)
class MultiStrategyComparison:
    """Aggregate result from :meth:`MultiStrategyRunner.run`."""

    start_date: date
    end_date: date
    run_date: date
    dry_run: bool
    backtest_run_id: int | None
    total_strategies: int
    strategy_results: list[StrategyResult] = field(default_factory=list)
    best_strategy_by_win_rate_5d: str | None = None
    best_strategy_by_avg_return_5d: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "start_date": self.start_date.isoformat(),
            "end_date": self.end_date.isoformat(),
            "run_date": self.run_date.isoformat(),
            "dry_run": self.dry_run,
            "backtest_run_id": self.backtest_run_id,
            "total_strategies": self.total_strategies,
            "best_strategy_by_win_rate_5d": self.best_strategy_by_win_rate_5d,
            "best_strategy_by_avg_return_5d": self.best_strategy_by_avg_return_5d,
            "strategy_results": [r.as_dict() for r in self.strategy_results],
        }


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------


class MultiStrategyRunner:
    """Run multiple strategies over the same period/universe and compare metrics.

    All strategies evaluate the **same** set of ``Recommendation`` rows
    (filtered by ``start_date``, ``end_date``, ``limit``).  The universe is
    therefore guaranteed to be identical across strategies — any difference in
    metrics reflects purely the strategy logic, not a data selection difference.
    """

    def __init__(
        self,
        session: Session,
        *,
        cost_model: CostModel | None = None,
        regime_market: str = DEFAULT_MARKET,
        with_regime_breakdown: bool = True,
        with_sector_breakdown: bool = True,
    ) -> None:
        self.session = session
        self._cost_model = cost_model or CostModel()
        self._regime_market = regime_market
        self._with_regime_breakdown = with_regime_breakdown
        self._with_sector_breakdown = with_sector_breakdown
        self._run_repo = BacktestRunRepository(session)

    def run(
        self,
        *,
        strategies: list[StrategyInterface],
        start_date: date,
        end_date: date,
        dry_run: bool = True,
        limit: int | None = None,
        run_date: date | None = None,
    ) -> MultiStrategyComparison:
        """Execute all strategies on the same universe and return a comparison.

        Per-strategy :class:`BacktestEngine` runs are always ``dry_run=True``.
        If ``dry_run=False`` here, one ``BacktestRun`` row is created for the
        entire comparison with ``strategy_name="MULTI"``.
        """

        # Pre-fetch recommendations+sector once so sector breakdown is O(1) per
        # strategy (pure in-memory evaluation after initial DB fetch).
        rec_rows: list = []
        returns_map: dict[int, Decimal | None] = {}
        if self._with_sector_breakdown and strategies:
            rec_rows = self._fetch_recs_with_sector(start_date, end_date, limit)
            returns_map = self._fetch_returns_map([row[0].id for row in rec_rows])

        strategy_results: list[StrategyResult] = []
        for strategy in strategies:
            engine = BacktestEngine(
                self.session,
                cost_model=self._cost_model,
                regime_market=self._regime_market,
            )
            summary = engine.run(
                strategy=strategy,
                start_date=start_date,
                end_date=end_date,
                limit=limit,
                dry_run=True,
            )

            sector_breakdown: list[SectorBreakdownEntry] = []
            if self._with_sector_breakdown:
                triples: list[tuple[str | None, str, Decimal | None]] = []
                for row in rec_rows:
                    rec, _run, snapshot, sector = row[0], row[1], row[2], row[3]
                    score_snapshot = build_score_snapshot(rec, snapshot)
                    signal = strategy.evaluate(score_snapshot)
                    triples.append((sector, signal.action, returns_map.get(rec.id)))
                sector_breakdown = aggregate_sector_breakdown(triples)

            strategy_results.append(
                StrategyResult(
                    strategy_name=summary.strategy_name,
                    strategy_version=summary.strategy_version,
                    signal_count=summary.signal_count,
                    buy_count=summary.buy_count,
                    pass_count=summary.pass_count,
                    avoid_count=summary.avoid_count,
                    win_rate_1d=summary.win_rate_1d,
                    win_rate_3d=summary.win_rate_3d,
                    win_rate_5d=summary.win_rate_5d,
                    win_rate_20d=summary.win_rate_20d,
                    avg_return_1d=summary.avg_return_1d,
                    avg_return_3d=summary.avg_return_3d,
                    avg_return_5d=summary.avg_return_5d,
                    avg_return_20d=summary.avg_return_20d,
                    cost_adjusted_avg_return_5d=summary.cost_adjusted_avg_return_5d,
                    max_drawdown=summary.max_drawdown,
                    regime_breakdown=summary.regime_breakdown if self._with_regime_breakdown else [],
                    sector_breakdown=sector_breakdown,
                )
            )

        best_by_wr, best_by_ar = _find_best(strategy_results)

        backtest_run_id: int | None = None
        if not dry_run and strategy_results:
            _run_date = run_date or _today()
            strategy_names = [s.name for s in strategies]
            ref = strategy_results[0]

            run_record = self._run_repo.create(
                strategy_name="MULTI",
                strategy_version="multi",
                run_date=_run_date,
                start_date=start_date,
                end_date=end_date,
                status=STATUS_DRY_RUN,
                config_json={
                    "mode": "multi_strategy_comparison",
                    "strategies": strategy_names,
                    "with_regime_breakdown": self._with_regime_breakdown,
                    "with_sector_breakdown": self._with_sector_breakdown,
                    "limit": limit,
                    "cost_model_version": self._cost_model.version,
                    "regime_market": self._regime_market,
                },
            )
            self._run_repo.mark_finished(
                run_record,
                signal_count=ref.signal_count,
                buy_count=0,
                avoid_count=0,
                pass_count=0,
                win_rate_1d=None,
                win_rate_3d=None,
                win_rate_5d=None,
                win_rate_20d=None,
                avg_return_1d=None,
                avg_return_3d=None,
                avg_return_5d=None,
                avg_return_20d=None,
                max_drawdown=None,
                summary_json={
                    "mode": "multi_strategy_comparison",
                    "total_strategies": len(strategy_results),
                    "best_strategy_by_win_rate_5d": best_by_wr,
                    "best_strategy_by_avg_return_5d": best_by_ar,
                    "multi_strategy_comparison": [r.as_dict() for r in strategy_results],
                    "notes": BUY_ONLY_METRICS_NOTE,
                },
            )
            backtest_run_id = run_record.id

        return MultiStrategyComparison(
            start_date=start_date,
            end_date=end_date,
            run_date=run_date or _today(),
            dry_run=dry_run,
            backtest_run_id=backtest_run_id,
            total_strategies=len(strategy_results),
            strategy_results=strategy_results,
            best_strategy_by_win_rate_5d=best_by_wr,
            best_strategy_by_avg_return_5d=best_by_ar,
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _fetch_recs_with_sector(
        self,
        start_date: date | None,
        end_date: date | None,
        limit: int | None,
    ) -> list:
        """Return rows of (Recommendation, RecommendationRun, DataSnapshot|None, sector|None).

        Uses the same ordering and filter as :meth:`BacktestEngine._fetch_recommendations`
        so the universe is identical for sector breakdown and the per-strategy BacktestEngine runs.
        """
        stmt = (
            select(Recommendation, RecommendationRun, DataSnapshot, Stock.sector)
            .join(RecommendationRun, Recommendation.run_id == RecommendationRun.run_id)
            .outerjoin(DataSnapshot, Recommendation.snapshot_id == DataSnapshot.snapshot_id)
            .outerjoin(Stock, Recommendation.symbol == Stock.symbol)
        )
        if start_date is not None:
            stmt = stmt.where(RecommendationRun.run_date >= start_date)
        if end_date is not None:
            stmt = stmt.where(RecommendationRun.run_date <= end_date)
        stmt = stmt.order_by(
            desc(RecommendationRun.run_date),
            desc(RecommendationRun.run_id),
            Recommendation.rank,
        )
        if limit is not None and limit > 0:
            stmt = stmt.limit(limit)
        return list(self.session.execute(stmt).all())

    def _fetch_returns_map(self, rec_ids: list[int]) -> dict[int, Decimal | None]:
        """Bulk-fetch 5-day close returns for the given recommendation IDs."""
        if not rec_ids:
            return {}
        rows = self.session.execute(
            select(RecommendationResult.recommendation_id, RecommendationResult.close_return)
            .where(
                RecommendationResult.recommendation_id.in_(rec_ids),
                RecommendationResult.days_after == 5,
            )
        ).all()
        return {row[0]: row[1] for row in rows}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _find_best(
    results: list[StrategyResult],
) -> tuple[str | None, str | None]:
    """Return (best_by_win_rate_5d, best_by_avg_return_5d) strategy names.

    Ties broken by the natural order of ``results`` (first strategy wins).
    Returns ``None`` when no strategy has a non-None value for that metric.
    """
    wr_candidates = [(r.strategy_name, r.win_rate_5d) for r in results if r.win_rate_5d is not None]
    ar_candidates = [(r.strategy_name, r.avg_return_5d) for r in results if r.avg_return_5d is not None]
    best_wr = max(wr_candidates, key=lambda x: x[1])[0] if wr_candidates else None
    best_ar = max(ar_candidates, key=lambda x: x[1])[0] if ar_candidates else None
    return best_wr, best_ar


def _dstr(v: Decimal | None) -> str | None:
    return str(v) if v is not None else None


def _today() -> date:
    from datetime import UTC, datetime as _dt

    return _dt.now(UTC).date()


__all__ = [
    "MultiStrategyComparison",
    "MultiStrategyRunner",
    "StrategyResult",
]
