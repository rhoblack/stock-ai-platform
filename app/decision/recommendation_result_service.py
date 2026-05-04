"""RecommendationResultService — Phase 5 follow-up post-recommendation performance.

Walks every recommendation generated within ``lookback_days`` and computes
1 / 3 / 5 / 20 day-after returns against ``daily_prices``. Results are upserted
into ``recommendation_results`` keyed on (recommendation_id, days_after) so the
job can re-run safely; PENDING rows are re-evaluated as more daily price data
becomes available.

Boundary rules (Phase 5 follow-up):
    * No KIS API call.
    * No recommendation / holding / scoring logic changes.
    * No Telegram dispatch, no AI calls, no order placement.
    * Result text is purely numeric — no investment advice phrasing.

Reference price selection:
    * Priority 1: ``daily_prices`` row with date == run.run_date for the symbol.
    * Priority 2: most recent ``daily_prices`` row with date ≤ run.run_date
      within a 14-day lookback (handles weekends / holidays where the run
      fires on a non-trading day).
    * If neither exists the recommendation cannot be evaluated yet — every
      days_after row is upserted as PENDING with all returns ``None``.

Result status (per days_after):
    * PENDING — verification window has no price data yet, OR no clear
      signal was hit.
    * SUCCESS — ``high_return ≥ +3%`` OR ``close_return ≥ +1%`` within window.
    * FAILED — ``low_return ≤ -5%`` (downside priority over upside).

Computations are in ``Decimal`` and quantized to 4 decimals to match the
``Numeric(12, 4)`` columns on ``recommendation_results``.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal

from app.data.repositories.daily_prices import DailyPriceRepository
from app.data.repositories.recommendations import (
    RecommendationRepository,
    RecommendationResultRepository,
    RecommendationRunRepository,
)
from app.db.models import DailyPrice, Recommendation


_RETURN_QUANT = Decimal("0.0001")

RESULT_STATUS_PENDING = "PENDING"
RESULT_STATUS_SUCCESS = "SUCCESS"
RESULT_STATUS_FAILED = "FAILED"


@dataclass(frozen=True)
class RecommendationResultRunResult:
    as_of: date
    processed_runs: int
    processed_recommendations: int
    upserted_results: int
    pending_count: int
    success_count: int
    failed_count: int
    skipped_no_reference: int


@dataclass(frozen=True)
class _ComputedResult:
    result_date: date
    open_return: Decimal | None
    high_return: Decimal | None
    low_return: Decimal | None
    close_return: Decimal | None
    max_return: Decimal | None
    max_drawdown: Decimal | None
    result_status: str


def _quantize(value: Decimal | None) -> Decimal | None:
    if value is None:
        return None
    return value.quantize(_RETURN_QUANT, rounding=ROUND_HALF_UP)


def _pct_change(value: Decimal, base: Decimal) -> Decimal:
    return (value - base) / base * Decimal("100")


class RecommendationResultService:
    DEFAULT_DAYS_AFTER: tuple[int, ...] = (1, 3, 5, 20)
    DEFAULT_LOOKBACK_DAYS = 60
    REFERENCE_LOOKBACK_DAYS = 14
    VERIFICATION_BUFFER_DAYS = 5  # extra calendar days to absorb weekends/holidays

    SUCCESS_HIGH_THRESHOLD = Decimal("3")
    SUCCESS_CLOSE_THRESHOLD = Decimal("1")
    FAILED_LOW_THRESHOLD = Decimal("-5")

    def __init__(
        self,
        *,
        recommendation_run_repository: RecommendationRunRepository,
        recommendation_repository: RecommendationRepository,
        recommendation_result_repository: RecommendationResultRepository,
        daily_price_repository: DailyPriceRepository,
    ) -> None:
        self._run_repo = recommendation_run_repository
        self._rec_repo = recommendation_repository
        self._result_repo = recommendation_result_repository
        self._price_repo = daily_price_repository

    def update_results(
        self,
        *,
        as_of: date,
        days_after: tuple[int, ...] | None = None,
        lookback_days: int = DEFAULT_LOOKBACK_DAYS,
    ) -> RecommendationResultRunResult:
        target_days = days_after or self.DEFAULT_DAYS_AFTER
        cutoff = as_of - timedelta(days=lookback_days)

        runs = self._run_repo.list_by_date_range(
            start_date=cutoff,
            end_date=as_of,
        )

        processed_recommendations = 0
        upserted = 0
        pending = 0
        success = 0
        failed = 0
        skipped_no_reference = 0

        for run in runs:
            recommendations = self._rec_repo.list_by_run_id(run.run_id)
            for rec in recommendations:
                processed_recommendations += 1
                reference = self._resolve_reference(
                    symbol=rec.symbol,
                    run_date=run.run_date,
                )
                if reference is None:
                    skipped_no_reference += 1
                    for n in target_days:
                        self._result_repo.upsert(
                            recommendation_id=rec.id,
                            days_after=n,
                            result_date=as_of,
                            result_status=RESULT_STATUS_PENDING,
                        )
                        upserted += 1
                        pending += 1
                    continue

                reference_date, reference_close = reference
                for n in target_days:
                    computed = self._compute_for_days_after(
                        rec=rec,
                        reference_date=reference_date,
                        reference_close=reference_close,
                        days_after=n,
                        as_of=as_of,
                    )
                    self._result_repo.upsert(
                        recommendation_id=rec.id,
                        days_after=n,
                        result_date=computed.result_date,
                        open_return=computed.open_return,
                        high_return=computed.high_return,
                        low_return=computed.low_return,
                        close_return=computed.close_return,
                        max_return=computed.max_return,
                        max_drawdown=computed.max_drawdown,
                        result_status=computed.result_status,
                    )
                    upserted += 1
                    if computed.result_status == RESULT_STATUS_SUCCESS:
                        success += 1
                    elif computed.result_status == RESULT_STATUS_FAILED:
                        failed += 1
                    else:
                        pending += 1

        return RecommendationResultRunResult(
            as_of=as_of,
            processed_runs=len(runs),
            processed_recommendations=processed_recommendations,
            upserted_results=upserted,
            pending_count=pending,
            success_count=success,
            failed_count=failed,
            skipped_no_reference=skipped_no_reference,
        )

    def _resolve_reference(
        self,
        *,
        symbol: str,
        run_date: date,
    ) -> tuple[date, Decimal] | None:
        exact = self._price_repo.get_by_symbol_date(symbol, run_date)
        if exact is not None:
            return exact.date, exact.close
        fallback = self._price_repo.get_latest_on_or_before(
            symbol=symbol,
            target_date=run_date,
            lookback_days=self.REFERENCE_LOOKBACK_DAYS,
        )
        if fallback is None:
            return None
        return fallback.date, fallback.close

    def _compute_for_days_after(
        self,
        *,
        rec: Recommendation,
        reference_date: date,
        reference_close: Decimal,
        days_after: int,
        as_of: date,
    ) -> _ComputedResult:
        target_date = reference_date + timedelta(days=days_after)
        bars = self._price_repo.list_in_range(
            symbol=rec.symbol,
            start_date=reference_date + timedelta(days=1),
            end_date=target_date + timedelta(days=self.VERIFICATION_BUFFER_DAYS),
        )
        bars_in_window = [b for b in bars if b.date <= target_date]
        if not bars_in_window:
            # No price has appeared inside the verification window yet.
            return _ComputedResult(
                result_date=as_of,
                open_return=None,
                high_return=None,
                low_return=None,
                close_return=None,
                max_return=None,
                max_drawdown=None,
                result_status=RESULT_STATUS_PENDING,
            )

        verification = bars_in_window[-1]
        open_return = _pct_change(verification.open, reference_close)
        close_return = _pct_change(verification.close, reference_close)
        max_high = max(b.high for b in bars_in_window)
        min_low = min(b.low for b in bars_in_window)
        high_return = _pct_change(max_high, reference_close)
        low_return = _pct_change(min_low, reference_close)

        peak = max(reference_close, max_high)
        max_drawdown = _pct_change(min_low, peak)

        status = self._classify_status(
            high_return=high_return,
            low_return=low_return,
            close_return=close_return,
        )

        return _ComputedResult(
            result_date=verification.date,
            open_return=_quantize(open_return),
            high_return=_quantize(high_return),
            low_return=_quantize(low_return),
            close_return=_quantize(close_return),
            max_return=_quantize(high_return),
            max_drawdown=_quantize(max_drawdown),
            result_status=status,
        )

    @classmethod
    def _classify_status(
        cls,
        *,
        high_return: Decimal,
        low_return: Decimal,
        close_return: Decimal,
    ) -> str:
        if low_return <= cls.FAILED_LOW_THRESHOLD:
            return RESULT_STATUS_FAILED
        if (
            high_return >= cls.SUCCESS_HIGH_THRESHOLD
            or close_return >= cls.SUCCESS_CLOSE_THRESHOLD
        ):
            return RESULT_STATUS_SUCCESS
        return RESULT_STATUS_PENDING
