"""WalkForwardBacktestEngine — v0.12 Phase B.

Splits a date range into a sequence of IS/OOS (train/validate) fold pairs and
runs the given strategy over each window using the existing BacktestEngine.
Fold metadata is stored in ``backtest_runs.summary_json`` under the key
``walk_forward_folds`` — no new DB columns or Alembic revisions.

Fold generation
---------------
* ``train_window_days`` (default 60): inclusive calendar-day span of the
  in-sample window.
* ``validate_window_days`` (default 20): inclusive calendar-day span of the
  out-of-sample window.
* ``gap_days`` (default 0): calendar days between ``train_end`` and
  ``validate_start``.  A gap of 0 means ``validate_start = train_end + 1``.
* Each step slides forward by ``validate_window_days`` so OOS periods never
  overlap.
* Fold generation stops when ``validate_end > end_date``.

Side-effect policy
------------------
* Per-fold BacktestEngine runs are **always** dry (no per-fold DB rows).
* ``dry_run=True`` (default): no DB writes at the walk-forward level either.
* ``dry_run=False``: persists exactly ONE ``BacktestRun`` row per call, with
  aggregate OOS metrics in the top-level columns and full fold detail in
  ``summary_json["walk_forward_folds"]``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy.orm import Session

from app.backtest.cost_model import CostModel
from app.backtest.engine import (
    BUY_ONLY_METRICS_NOTE,
    BacktestEngine,
    BacktestRunSummary,
)
from app.backtest.regime_split import DEFAULT_MARKET
from app.data.repositories.backtest_runs import BacktestRunRepository, STATUS_DRY_RUN
from app.strategy.interfaces import StrategyInterface


# ---------------------------------------------------------------------------
# Result types
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class FoldResult:
    """Metrics for one IS/OOS fold pair."""

    fold_index: int
    train_start: date
    train_end: date
    validate_start: date
    validate_end: date
    is_metrics: BacktestRunSummary
    oos_metrics: BacktestRunSummary
    is_oos_gap: int
    signal_count: int
    buy_count: int

    def as_dict(self) -> dict[str, Any]:
        return {
            "fold_index": self.fold_index,
            "train_start": self.train_start.isoformat(),
            "train_end": self.train_end.isoformat(),
            "validate_start": self.validate_start.isoformat(),
            "validate_end": self.validate_end.isoformat(),
            "is_oos_gap": self.is_oos_gap,
            "is_signal_count": self.is_metrics.signal_count,
            "is_buy_count": self.is_metrics.buy_count,
            "is_win_rate_5d": _dstr(self.is_metrics.win_rate_5d),
            "is_avg_return_5d": _dstr(self.is_metrics.avg_return_5d),
            "oos_signal_count": self.oos_metrics.signal_count,
            "oos_buy_count": self.oos_metrics.buy_count,
            "oos_win_rate_5d": _dstr(self.oos_metrics.win_rate_5d),
            "oos_avg_return_5d": _dstr(self.oos_metrics.avg_return_5d),
        }


@dataclass(frozen=True)
class WalkForwardSummary:
    """Aggregate result from WalkForwardBacktestEngine.run()."""

    strategy_name: str
    strategy_version: str
    run_date: date
    start_date: date
    end_date: date
    train_window_days: int
    validate_window_days: int
    gap_days: int
    dry_run: bool
    backtest_run_id: int | None
    total_folds: int
    fold_results: list[FoldResult] = field(default_factory=list)
    avg_oos_win_rate_5d: Decimal | None = None
    avg_oos_avg_return_5d: Decimal | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "strategy_name": self.strategy_name,
            "strategy_version": self.strategy_version,
            "run_date": self.run_date.isoformat(),
            "start_date": self.start_date.isoformat(),
            "end_date": self.end_date.isoformat(),
            "train_window_days": self.train_window_days,
            "validate_window_days": self.validate_window_days,
            "gap_days": self.gap_days,
            "dry_run": self.dry_run,
            "backtest_run_id": self.backtest_run_id,
            "total_folds": self.total_folds,
            "avg_oos_win_rate_5d": _dstr(self.avg_oos_win_rate_5d),
            "avg_oos_avg_return_5d": _dstr(self.avg_oos_avg_return_5d),
            "fold_results": [f.as_dict() for f in self.fold_results],
        }


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------


class WalkForwardBacktestEngine:
    """Walk-forward validation: IS metrics train strategy, OOS metrics validate it."""

    def __init__(
        self,
        session: Session,
        *,
        cost_model: CostModel | None = None,
        regime_market: str = DEFAULT_MARKET,
        train_window_days: int = 60,
        validate_window_days: int = 20,
        gap_days: int = 0,
    ) -> None:
        self.session = session
        self._cost_model = cost_model or CostModel()
        self._regime_market = regime_market
        self.train_window_days = train_window_days
        self.validate_window_days = validate_window_days
        self.gap_days = gap_days
        self._run_repo = BacktestRunRepository(session)

    def run(
        self,
        *,
        strategy: StrategyInterface,
        start_date: date,
        end_date: date,
        dry_run: bool = True,
        run_date: date | None = None,
    ) -> WalkForwardSummary:
        """Execute walk-forward validation and optionally persist one BacktestRun."""

        folds_spec = generate_folds(
            start_date,
            end_date,
            self.train_window_days,
            self.validate_window_days,
            self.gap_days,
        )

        fold_results: list[FoldResult] = []
        for fold_index, train_start, train_end, validate_start, validate_end in folds_spec:
            engine = BacktestEngine(
                self.session,
                cost_model=self._cost_model,
                regime_market=self._regime_market,
            )
            is_metrics = engine.run(
                strategy=strategy,
                start_date=train_start,
                end_date=train_end,
                dry_run=True,
            )
            oos_metrics = engine.run(
                strategy=strategy,
                start_date=validate_start,
                end_date=validate_end,
                dry_run=True,
            )
            fold_results.append(
                FoldResult(
                    fold_index=fold_index,
                    train_start=train_start,
                    train_end=train_end,
                    validate_start=validate_start,
                    validate_end=validate_end,
                    is_metrics=is_metrics,
                    oos_metrics=oos_metrics,
                    is_oos_gap=self.gap_days,
                    signal_count=oos_metrics.signal_count,
                    buy_count=oos_metrics.buy_count,
                )
            )

        avg_oos_win_rate_5d, avg_oos_avg_return_5d = _avg_oos_metrics(fold_results)

        backtest_run_id: int | None = None
        if not dry_run:
            _run_date = run_date or _today()
            total_signal_count = sum(f.oos_metrics.signal_count for f in fold_results)
            total_buy_count = sum(f.oos_metrics.buy_count for f in fold_results)
            total_pass_count = sum(f.oos_metrics.pass_count for f in fold_results)
            total_avoid_count = sum(f.oos_metrics.avoid_count for f in fold_results)

            run_record = self._run_repo.create(
                strategy_name=strategy.name,
                strategy_version=strategy.version,
                run_date=_run_date,
                start_date=start_date,
                end_date=end_date,
                status=STATUS_DRY_RUN,
                config_json={
                    "mode": "walk_forward",
                    "train_window_days": self.train_window_days,
                    "validate_window_days": self.validate_window_days,
                    "gap_days": self.gap_days,
                    "cost_model_version": self._cost_model.version,
                    "regime_market": self._regime_market,
                },
            )
            self._run_repo.mark_finished(
                run_record,
                signal_count=total_signal_count,
                buy_count=total_buy_count,
                avoid_count=total_avoid_count,
                pass_count=total_pass_count,
                win_rate_1d=None,
                win_rate_3d=None,
                win_rate_5d=avg_oos_win_rate_5d,
                win_rate_20d=None,
                avg_return_1d=None,
                avg_return_3d=None,
                avg_return_5d=avg_oos_avg_return_5d,
                avg_return_20d=None,
                max_drawdown=None,
                summary_json={
                    "mode": "walk_forward",
                    "total_folds": len(fold_results),
                    "avg_oos_win_rate_5d": _dstr(avg_oos_win_rate_5d),
                    "avg_oos_avg_return_5d": _dstr(avg_oos_avg_return_5d),
                    "walk_forward_folds": [f.as_dict() for f in fold_results],
                    "notes": BUY_ONLY_METRICS_NOTE,
                },
            )
            backtest_run_id = run_record.id

        return WalkForwardSummary(
            strategy_name=strategy.name,
            strategy_version=strategy.version,
            run_date=run_date or _today(),
            start_date=start_date,
            end_date=end_date,
            train_window_days=self.train_window_days,
            validate_window_days=self.validate_window_days,
            gap_days=self.gap_days,
            dry_run=dry_run,
            backtest_run_id=backtest_run_id,
            total_folds=len(fold_results),
            fold_results=fold_results,
            avg_oos_win_rate_5d=avg_oos_win_rate_5d,
            avg_oos_avg_return_5d=avg_oos_avg_return_5d,
        )


# ---------------------------------------------------------------------------
# Fold generation (public for testing)
# ---------------------------------------------------------------------------


def generate_folds(
    start_date: date,
    end_date: date,
    train_window_days: int,
    validate_window_days: int,
    gap_days: int,
) -> list[tuple[int, date, date, date, date]]:
    """Return a list of (fold_index, train_start, train_end, validate_start, validate_end).

    Each tuple covers one IS/OOS pair. The list is empty when the date range
    is too short to fit at least one complete pair.

    Sliding rule: each step advances ``cursor`` by ``validate_window_days`` so
    consecutive OOS windows abut without overlap.
    """
    folds: list[tuple[int, date, date, date, date]] = []
    fold_index = 0
    cursor = start_date
    while True:
        train_start = cursor
        train_end = train_start + timedelta(days=train_window_days - 1)
        validate_start = train_end + timedelta(days=gap_days + 1)
        validate_end = validate_start + timedelta(days=validate_window_days - 1)
        if validate_end > end_date:
            break
        folds.append((fold_index, train_start, train_end, validate_start, validate_end))
        fold_index += 1
        cursor = cursor + timedelta(days=validate_window_days)
    return folds


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _avg_oos_metrics(
    fold_results: list[FoldResult],
) -> tuple[Decimal | None, Decimal | None]:
    wr_values = [f.oos_metrics.win_rate_5d for f in fold_results if f.oos_metrics.win_rate_5d is not None]
    ar_values = [f.oos_metrics.avg_return_5d for f in fold_results if f.oos_metrics.avg_return_5d is not None]
    avg_wr = (sum(wr_values) / Decimal(len(wr_values))).quantize(Decimal("0.0001")) if wr_values else None
    avg_ar = (sum(ar_values) / Decimal(len(ar_values))).quantize(Decimal("0.0001")) if ar_values else None
    return avg_wr, avg_ar


def _dstr(value: Decimal | None) -> str | None:
    return str(value) if value is not None else None


def _today() -> date:
    from datetime import UTC, datetime as _dt

    return _dt.now(UTC).date()


__all__ = [
    "FoldResult",
    "WalkForwardBacktestEngine",
    "WalkForwardSummary",
    "generate_folds",
]
