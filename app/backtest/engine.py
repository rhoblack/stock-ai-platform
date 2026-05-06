"""BacktestEngine — v0.7 Phase B.

Replays a strategy across past ``Recommendation`` rows + their
``RecommendationResult`` horizon returns to compute simple performance metrics
(win-rate / avg-return / max-drawdown).

Statistics policy
-----------------
* ``signal_count``, ``buy_count``, ``pass_count``, ``avoid_count`` count every
  evaluated signal.
* ``win_rate_*`` and ``avg_return_*`` are scoped to **BUY signals only** and
  exclude horizons where the underlying ``recommendation_results.close_return``
  is NULL (those increment ``missing_result_count`` per horizon).
* ``max_drawdown`` aggregates the **minimum** ``recommendation_results.max_drawdown``
  observed across BUY signals (i.e. worst-case excursion in the BUY universe).
* If a horizon has zero non-null BUY samples its ``win_rate_*`` /
  ``avg_return_*`` value is ``None`` (not zero) so callers can distinguish
  "no data" from "all losses".

Side-effect policy
------------------
* ``dry_run=True`` (default): no DB writes. The summary still includes every
  field the persisted version would, but ``backtest_run_id`` is ``None``.
* ``dry_run=False``: persists one ``BacktestRun`` + N ``BacktestResult`` rows
  in a single ``session.flush()`` — caller controls ``commit``/``rollback``.
* Engine never calls KIS / DART / Telegram / brokers / external HTTP. It only
  reads from existing repositories already populated by earlier cycles.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import Any

from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.backtest.cost_model import CostModel
from app.backtest.regime_split import (
    DEFAULT_MARKET,
    UNCLASSIFIED_BUCKET,
    assign_regime,
    display_bucket,
)
from app.data.repositories.backtest_results import BacktestResultRepository
from app.data.repositories.backtest_runs import (
    BacktestRunRepository,
    STATUS_DRY_RUN,
)
from app.db.models import (
    BacktestResult,
    DataSnapshot,
    Recommendation,
    RecommendationResult,
    RecommendationRun,
)
from app.strategy.interfaces import (
    STRATEGY_ACTION_AVOID,
    STRATEGY_ACTION_BUY,
    STRATEGY_ACTION_PASS,
    ScoreSnapshot,
    StrategyInterface,
)


BUY_ONLY_METRICS_NOTE = (
    "win_rate / avg_return / max_drawdown are computed over BUY signals only. "
    "PASS / AVOID signals are counted in *_count but excluded from these aggregates."
)

_HORIZONS: tuple[int, ...] = (1, 3, 5, 20)


@dataclass(frozen=True)
class RegimeBreakdownEntry:
    """Per-regime BUY metrics surfaced in ``BacktestRunSummary.regime_breakdown``."""

    regime: str
    buy_count: int
    win_rate_5d: Decimal | None
    avg_return_5d: Decimal | None
    cost_adjusted_avg_return_5d: Decimal | None

    def as_dict(self) -> dict[str, Any]:
        return {
            "regime": self.regime,
            "buy_count": self.buy_count,
            "win_rate_5d": _decimal_str(self.win_rate_5d),
            "avg_return_5d": _decimal_str(self.avg_return_5d),
            "cost_adjusted_avg_return_5d": _decimal_str(self.cost_adjusted_avg_return_5d),
        }


@dataclass(frozen=True)
class BacktestRunSummary:
    """Plain summary returned from ``BacktestEngine.run`` (no ORM dependency)."""

    strategy_name: str
    strategy_version: str
    run_date: date
    start_date: date | None
    end_date: date | None
    dry_run: bool
    backtest_run_id: int | None
    evaluated_recommendation_count: int
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
    max_drawdown: Decimal | None
    cost_model_version: str
    total_cost: Decimal
    cost_adjusted_avg_return_5d: Decimal | None
    regime_breakdown: list[RegimeBreakdownEntry] = field(default_factory=list)
    missing_result_count_per_horizon: dict[int, int] = field(default_factory=dict)
    notes: str = BUY_ONLY_METRICS_NOTE

    def as_dict(self) -> dict[str, Any]:
        return {
            "strategy_name": self.strategy_name,
            "strategy_version": self.strategy_version,
            "run_date": self.run_date.isoformat(),
            "start_date": self.start_date.isoformat() if self.start_date else None,
            "end_date": self.end_date.isoformat() if self.end_date else None,
            "dry_run": self.dry_run,
            "backtest_run_id": self.backtest_run_id,
            "evaluated_recommendation_count": self.evaluated_recommendation_count,
            "signal_count": self.signal_count,
            "buy_count": self.buy_count,
            "pass_count": self.pass_count,
            "avoid_count": self.avoid_count,
            "win_rate_1d": _decimal_str(self.win_rate_1d),
            "win_rate_3d": _decimal_str(self.win_rate_3d),
            "win_rate_5d": _decimal_str(self.win_rate_5d),
            "win_rate_20d": _decimal_str(self.win_rate_20d),
            "avg_return_1d": _decimal_str(self.avg_return_1d),
            "avg_return_3d": _decimal_str(self.avg_return_3d),
            "avg_return_5d": _decimal_str(self.avg_return_5d),
            "avg_return_20d": _decimal_str(self.avg_return_20d),
            "max_drawdown": _decimal_str(self.max_drawdown),
            "cost_model_version": self.cost_model_version,
            "total_cost": _decimal_str(self.total_cost),
            "cost_adjusted_avg_return_5d": _decimal_str(self.cost_adjusted_avg_return_5d),
            "regime_breakdown": [entry.as_dict() for entry in self.regime_breakdown],
            "missing_result_count_per_horizon": dict(
                self.missing_result_count_per_horizon,
            ),
            "notes": self.notes,
        }


def _decimal_str(value: Decimal | None) -> str | None:
    return str(value) if value is not None else None


# ---------------------------------------------------------------------------
# ScoreSnapshot construction helpers
# ---------------------------------------------------------------------------


def _safe_dict(value: Any) -> dict[str, Any] | None:
    return value if isinstance(value, dict) else None


def _safe_list_of_str(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value if isinstance(item, str)]


def build_score_snapshot(
    recommendation: Recommendation,
    snapshot: DataSnapshot | None,
) -> ScoreSnapshot:
    """Project a Recommendation row + its DataSnapshot into a ScoreSnapshot.

    All fields are best-effort: if a JSON key is missing or wrongly typed the
    resulting field is ``None`` / ``[]`` (strategies must already cope).

    The function never fetches new data — it only reads what the caller already
    loaded. No order-side fields (quantity / price / account / broker) are
    propagated; the strategy layer is order-blind by design.
    """

    market_context = (snapshot.market_context_json if snapshot is not None else None) or {}
    risk_summary = _safe_dict(market_context.get("risk_summary")) or {}
    risk_level = risk_summary.get("level")
    risk_flags = _safe_list_of_str(risk_summary.get("flags"))

    evidence = {
        "news_evidence": _safe_dict(market_context.get("news_evidence")),
        "disclosure_risk_evidence": _safe_dict(
            market_context.get("disclosure_risk_evidence"),
        ),
        "fundamental_evidence": _safe_dict(market_context.get("fundamental_evidence")),
        "earnings_evidence": _safe_dict(market_context.get("earnings_evidence")),
    }
    # Drop entirely-empty buckets so the strategy layer sees a tidy dict.
    evidence = {k: v for k, v in evidence.items() if v is not None}

    return ScoreSnapshot(
        symbol=recommendation.symbol,
        total_score=recommendation.total_score,
        grade=recommendation.grade,
        technical_score=recommendation.technical_score,
        news_score=recommendation.news_score,
        supply_score=recommendation.supply_score,
        fundamental_score=recommendation.fundamental_score,
        earnings_score=None,
        ai_score=recommendation.ai_score,
        report_score=None,
        theme_signal_score=None,
        risk_level=risk_level if isinstance(risk_level, str) else None,
        risk_flags=risk_flags,
        evidence=evidence or None,
    )


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------


class BacktestEngine:
    """Replay a strategy across past recommendations + horizon returns."""

    def __init__(
        self,
        session: Session,
        *,
        cost_model: CostModel | None = None,
        regime_market: str = DEFAULT_MARKET,
    ) -> None:
        self.session = session
        self._run_repo = BacktestRunRepository(session)
        self._result_repo = BacktestResultRepository(session)
        self._cost_model = cost_model or CostModel()
        self._regime_market = regime_market

    def run(
        self,
        *,
        strategy: StrategyInterface,
        start_date: date | None = None,
        end_date: date | None = None,
        dry_run: bool = True,
        limit: int | None = None,
        run_date: date | None = None,
    ) -> BacktestRunSummary:
        """Execute one strategy over recommendations in ``[start_date, end_date]``."""

        rows = self._fetch_recommendations(start_date, end_date, limit)

        # Materialize ScoreSnapshot + signals + horizon returns up front so we
        # can compute summary stats before deciding whether to persist.
        evaluated: list[_EvaluatedRow] = []
        for rec, run, snapshot in rows:
            score_snapshot = build_score_snapshot(rec, snapshot)
            signal = strategy.evaluate(score_snapshot)
            horizons = self._fetch_horizon_returns(rec.id)
            return_5d = horizons.get(5, _HorizonReturn()).close
            # Cost adjustment is BUY-only — PASS / AVOID rows leave the column
            # NULL so the persisted data does not imply we ever paid fees on
            # them.
            cost_adjusted_return_5d = (
                self._cost_model.apply(return_5d)
                if signal.action == STRATEGY_ACTION_BUY
                else None
            )
            regime = assign_regime(
                self.session,
                run.run_date,
                market=self._regime_market,
            )
            evaluated.append(
                _EvaluatedRow(
                    recommendation=rec,
                    run=run,
                    snapshot=snapshot,
                    signal_action=signal.action,
                    confidence=signal.confidence,
                    reason=signal.reason,
                    evidence=signal.evidence,
                    return_1d=horizons.get(1, _HorizonReturn()).close,
                    return_3d=horizons.get(3, _HorizonReturn()).close,
                    return_5d=return_5d,
                    return_20d=horizons.get(20, _HorizonReturn()).close,
                    max_drawdown=_min_max_drawdown(horizons),
                    result_status=horizons.get(5, _HorizonReturn()).status,
                    recommendation_result_id=horizons.get(5, _HorizonReturn()).result_id,
                    cost_adjusted_return_5d=cost_adjusted_return_5d,
                    regime=regime,
                ),
            )

        stats = _aggregate(evaluated)

        regime_breakdown = _build_regime_breakdown(evaluated, self._cost_model)

        backtest_run_id: int | None = None
        if not dry_run:
            run_record = self._run_repo.create(
                strategy_name=strategy.name,
                strategy_version=strategy.version,
                run_date=run_date or _today(),
                start_date=start_date,
                end_date=end_date,
                status=STATUS_DRY_RUN,  # mark_finished bumps this to SUCCESS
                config_json={
                    "limit": limit,
                    "horizons": list(_HORIZONS),
                    "cost_model_version": self._cost_model.version,
                    "regime_market": self._regime_market,
                },
            )
            self._persist_results(run_record.id, evaluated)
            self._run_repo.mark_finished(
                run_record,
                signal_count=stats.signal_count,
                buy_count=stats.buy_count,
                avoid_count=stats.avoid_count,
                pass_count=stats.pass_count,
                win_rate_1d=stats.win_rate[1],
                win_rate_3d=stats.win_rate[3],
                win_rate_5d=stats.win_rate[5],
                win_rate_20d=stats.win_rate[20],
                avg_return_1d=stats.avg_return[1],
                avg_return_3d=stats.avg_return[3],
                avg_return_5d=stats.avg_return[5],
                avg_return_20d=stats.avg_return[20],
                max_drawdown=stats.max_drawdown,
                summary_json={
                    "missing_result_count_per_horizon": dict(stats.missing_per_horizon),
                    "cost_model_version": self._cost_model.version,
                    "total_cost": str(self._cost_model.total_cost),
                    "cost_adjusted_avg_return_5d": _decimal_str(
                        stats.cost_adjusted_avg_return_5d,
                    ),
                    "regime_breakdown": [entry.as_dict() for entry in regime_breakdown],
                    "notes": BUY_ONLY_METRICS_NOTE,
                },
            )
            backtest_run_id = run_record.id

        return BacktestRunSummary(
            strategy_name=strategy.name,
            strategy_version=strategy.version,
            run_date=run_date or _today(),
            start_date=start_date,
            end_date=end_date,
            dry_run=dry_run,
            backtest_run_id=backtest_run_id,
            evaluated_recommendation_count=len(evaluated),
            signal_count=stats.signal_count,
            buy_count=stats.buy_count,
            pass_count=stats.pass_count,
            avoid_count=stats.avoid_count,
            win_rate_1d=stats.win_rate[1],
            win_rate_3d=stats.win_rate[3],
            win_rate_5d=stats.win_rate[5],
            win_rate_20d=stats.win_rate[20],
            avg_return_1d=stats.avg_return[1],
            avg_return_3d=stats.avg_return[3],
            avg_return_5d=stats.avg_return[5],
            avg_return_20d=stats.avg_return[20],
            max_drawdown=stats.max_drawdown,
            cost_model_version=self._cost_model.version,
            total_cost=self._cost_model.total_cost,
            cost_adjusted_avg_return_5d=stats.cost_adjusted_avg_return_5d,
            regime_breakdown=regime_breakdown,
            missing_result_count_per_horizon=dict(stats.missing_per_horizon),
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _fetch_recommendations(
        self,
        start_date: date | None,
        end_date: date | None,
        limit: int | None,
    ) -> list[tuple[Recommendation, RecommendationRun, DataSnapshot | None]]:
        statement = (
            select(Recommendation, RecommendationRun, DataSnapshot)
            .join(RecommendationRun, Recommendation.run_id == RecommendationRun.run_id)
            .outerjoin(
                DataSnapshot,
                Recommendation.snapshot_id == DataSnapshot.snapshot_id,
            )
        )
        if start_date is not None:
            statement = statement.where(RecommendationRun.run_date >= start_date)
        if end_date is not None:
            statement = statement.where(RecommendationRun.run_date <= end_date)
        statement = statement.order_by(
            desc(RecommendationRun.run_date),
            desc(RecommendationRun.run_id),
            Recommendation.rank,
        )
        if limit is not None and limit > 0:
            statement = statement.limit(limit)
        rows = list(self.session.execute(statement).all())
        return [(row[0], row[1], row[2]) for row in rows]

    def _fetch_horizon_returns(self, recommendation_id: int) -> dict[int, "_HorizonReturn"]:
        statement = select(RecommendationResult).where(
            RecommendationResult.recommendation_id == recommendation_id,
            RecommendationResult.days_after.in_(_HORIZONS),
        )
        out: dict[int, _HorizonReturn] = {}
        for row in self.session.execute(statement).scalars().all():
            out[row.days_after] = _HorizonReturn(
                close=row.close_return,
                status=row.result_status,
                max_drawdown=row.max_drawdown,
                result_id=row.id,
            )
        return out

    def _persist_results(
        self,
        backtest_run_id: int,
        evaluated: list["_EvaluatedRow"],
    ) -> None:
        records = [
            BacktestResult(
                backtest_run_id=backtest_run_id,
                symbol=row.recommendation.symbol,
                signal_action=row.signal_action,
                recommendation_id=row.recommendation.id,
                recommendation_result_id=row.recommendation_result_id,
                confidence=row.confidence,
                reason=row.reason,
                grade=row.recommendation.grade,
                total_score=row.recommendation.total_score,
                return_1d=row.return_1d,
                return_3d=row.return_3d,
                return_5d=row.return_5d,
                return_20d=row.return_20d,
                max_drawdown=row.max_drawdown,
                result_status=row.result_status,
                cost_adjusted_return_5d=row.cost_adjusted_return_5d,
                regime=row.regime,
                evidence_json=row.evidence,
            )
            for row in evaluated
        ]
        self._result_repo.bulk_insert(records)


# ---------------------------------------------------------------------------
# Internal dataclasses + aggregation
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class _HorizonReturn:
    close: Decimal | None = None
    status: str | None = None
    max_drawdown: Decimal | None = None
    result_id: int | None = None


@dataclass(frozen=True)
class _EvaluatedRow:
    recommendation: Recommendation
    run: RecommendationRun
    snapshot: DataSnapshot | None
    signal_action: str
    confidence: Decimal | None
    reason: str | None
    evidence: dict[str, Any] | None
    return_1d: Decimal | None
    return_3d: Decimal | None
    return_5d: Decimal | None
    return_20d: Decimal | None
    max_drawdown: Decimal | None
    result_status: str | None
    recommendation_result_id: int | None
    cost_adjusted_return_5d: Decimal | None
    regime: str | None


@dataclass(frozen=True)
class _AggregateStats:
    signal_count: int
    buy_count: int
    pass_count: int
    avoid_count: int
    win_rate: dict[int, Decimal | None]
    avg_return: dict[int, Decimal | None]
    max_drawdown: Decimal | None
    cost_adjusted_avg_return_5d: Decimal | None
    missing_per_horizon: dict[int, int]


def _aggregate(rows: list[_EvaluatedRow]) -> _AggregateStats:
    signal_count = len(rows)
    buy_count = sum(1 for r in rows if r.signal_action == STRATEGY_ACTION_BUY)
    pass_count = sum(1 for r in rows if r.signal_action == STRATEGY_ACTION_PASS)
    avoid_count = sum(1 for r in rows if r.signal_action == STRATEGY_ACTION_AVOID)

    buy_rows = [r for r in rows if r.signal_action == STRATEGY_ACTION_BUY]

    win_rate: dict[int, Decimal | None] = {}
    avg_return: dict[int, Decimal | None] = {}
    missing_per_horizon: dict[int, int] = {}
    for horizon in _HORIZONS:
        returns = [_horizon_value(r, horizon) for r in buy_rows]
        non_null = [v for v in returns if v is not None]
        missing_per_horizon[horizon] = len(returns) - len(non_null)
        if non_null:
            wins = sum(1 for v in non_null if v > 0)
            win_rate[horizon] = (Decimal(wins) / Decimal(len(non_null))).quantize(
                Decimal("0.0001"),
            )
            avg_return[horizon] = (sum(non_null) / Decimal(len(non_null))).quantize(
                Decimal("0.0001"),
            )
        else:
            win_rate[horizon] = None
            avg_return[horizon] = None

    drawdowns = [r.max_drawdown for r in buy_rows if r.max_drawdown is not None]
    aggregate_drawdown = min(drawdowns) if drawdowns else None

    cost_adjusted_values = [
        r.cost_adjusted_return_5d for r in buy_rows if r.cost_adjusted_return_5d is not None
    ]
    cost_adjusted_avg_return_5d = (
        (sum(cost_adjusted_values) / Decimal(len(cost_adjusted_values))).quantize(
            Decimal("0.0001"),
        )
        if cost_adjusted_values
        else None
    )

    return _AggregateStats(
        signal_count=signal_count,
        buy_count=buy_count,
        pass_count=pass_count,
        avoid_count=avoid_count,
        win_rate=win_rate,
        avg_return=avg_return,
        max_drawdown=aggregate_drawdown,
        cost_adjusted_avg_return_5d=cost_adjusted_avg_return_5d,
        missing_per_horizon=missing_per_horizon,
    )


def _build_regime_breakdown(
    rows: list[_EvaluatedRow],
    cost_model: CostModel,
) -> list[RegimeBreakdownEntry]:
    """Group BUY rows by regime bucket → per-bucket win_rate / avg_return.

    NULL ``regime`` values fold into :data:`UNCLASSIFIED_BUCKET`. Buckets are
    returned sorted by ``buy_count desc`` then bucket name asc so the engine
    output is deterministic across runs.
    """

    buy_rows = [r for r in rows if r.signal_action == STRATEGY_ACTION_BUY]
    by_bucket: dict[str, list[_EvaluatedRow]] = {}
    for row in buy_rows:
        bucket = display_bucket(row.regime)
        by_bucket.setdefault(bucket, []).append(row)

    entries: list[RegimeBreakdownEntry] = []
    for bucket, rows_in_bucket in by_bucket.items():
        five_day_returns = [r.return_5d for r in rows_in_bucket if r.return_5d is not None]
        cost_returns = [
            r.cost_adjusted_return_5d
            for r in rows_in_bucket
            if r.cost_adjusted_return_5d is not None
        ]
        if five_day_returns:
            wins = sum(1 for v in five_day_returns if v > 0)
            win_rate_5d = (Decimal(wins) / Decimal(len(five_day_returns))).quantize(
                Decimal("0.0001"),
            )
            avg_return_5d = (
                sum(five_day_returns) / Decimal(len(five_day_returns))
            ).quantize(Decimal("0.0001"))
        else:
            win_rate_5d = None
            avg_return_5d = None
        cost_adjusted = (
            (sum(cost_returns) / Decimal(len(cost_returns))).quantize(Decimal("0.0001"))
            if cost_returns
            else None
        )
        entries.append(
            RegimeBreakdownEntry(
                regime=bucket,
                buy_count=len(rows_in_bucket),
                win_rate_5d=win_rate_5d,
                avg_return_5d=avg_return_5d,
                cost_adjusted_avg_return_5d=cost_adjusted,
            ),
        )

    entries.sort(key=lambda e: (-e.buy_count, e.regime))
    return entries


def _horizon_value(row: _EvaluatedRow, horizon: int) -> Decimal | None:
    return {
        1: row.return_1d,
        3: row.return_3d,
        5: row.return_5d,
        20: row.return_20d,
    }[horizon]


def _min_max_drawdown(horizons: dict[int, _HorizonReturn]) -> Decimal | None:
    """Return the worst (minimum) max_drawdown across observed horizons.

    ``recommendation_results.max_drawdown`` is stored as a negative value
    (or zero); the minimum is the deepest excursion.
    """

    drawdowns = [h.max_drawdown for h in horizons.values() if h.max_drawdown is not None]
    return min(drawdowns) if drawdowns else None


def _today() -> date:
    from datetime import UTC, datetime as _dt

    return _dt.now(UTC).date()


__all__ = [
    "BUY_ONLY_METRICS_NOTE",
    "BacktestEngine",
    "BacktestRunSummary",
    "RegimeBreakdownEntry",
    "build_score_snapshot",
]
