"""HoldingCheckEngine v0.1 — Phase 5-3 pre-/post-market check generator.

Reads active ``holdings``, joins with the latest ``daily_prices`` row (for
current_price) and the latest ``stock_indicators`` row (for technical signals),
runs a two-pass scoring flow with ``RiskEngine`` between passes:

    Pass 1: ScoringEngine.score_holding(technical_only) → weighted_total
    Pass 2: RiskEngine.evaluate_holding(...) → risk_penalty + risk_flags
    Pass 3: ScoringEngine.score_holding(technical_only, risk_penalty=...) → final

The result is persisted to ``holding_checks`` with HOLD / WATCH / REDUCE /
SELL_REVIEW decision derived from the post-penalty grade, plus a parallel
``data_snapshots`` and ``decision_logs`` record.

Boundary rules (Phase 5-3):
    * No KIS API call.
    * No technical indicator recomputation (read-only against ``stock_indicators``).
    * Recommendation logic untouched.
    * No Telegram, AI/LLM, or order placement.
    * Decision text stays observational ("보유 유지" / "관찰 필요" /
      "비중 축소 검토" / "매도 검토"); never frames a sell directive.
    * RiskEngine produces flags only; nothing here blocks or executes orders.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from app.data.repositories.daily_prices import DailyPriceRepository
from app.data.repositories.decision_logs import DecisionLogRepository
from app.data.repositories.holdings import HoldingRepository
from app.data.repositories.holding_checks import HoldingCheckRepository
from app.data.repositories.snapshots import DataSnapshotRepository
from app.data.repositories.stock_indicators import StockIndicatorRepository
from app.db.models import (
    DailyPrice,
    DataSnapshot,
    DecisionLog,
    Holding,
    HoldingCheck,
    StockIndicator,
)
from app.decision.risk_engine import (
    RISK_FLAG_MA20_BREAKDOWN,
    RISK_FLAG_SCORE_DROP,
    RISK_FLAG_STOP_LOSS_NEAR,
    RiskAssessment,
    RiskEngine,
)
from app.decision.scoring_engine import (
    HoldingScoreInputs,
    ScoringEngine,
)


CHECK_TYPE_PRE_MARKET = "PRE_MARKET"
CHECK_TYPE_POST_MARKET = "POST_MARKET"
_VALID_CHECK_TYPES = {CHECK_TYPE_PRE_MARKET, CHECK_TYPE_POST_MARKET}

_SNAPSHOT_TYPE_HOLDING_CHECK = "HOLDING_CHECK"
_DECISION_TYPE_HOLDING = "HOLDING"

DECISION_HOLD = "HOLD"
DECISION_WATCH = "WATCH"
DECISION_REDUCE = "REDUCE"
DECISION_SELL_REVIEW = "SELL_REVIEW"

# Backward-compatible alert-name aliases (string values match RiskEngine flags).
ALERT_SCORE_DROP = RISK_FLAG_SCORE_DROP
ALERT_MA20_BREAKDOWN = RISK_FLAG_MA20_BREAKDOWN
ALERT_STOP_LOSS_NEAR = RISK_FLAG_STOP_LOSS_NEAR

_RETURN_RATE_QUANT = Decimal("0.0001")


@dataclass(frozen=True)
class HoldingCheckResult:
    check_date: date
    check_type: str
    saved_count: int
    skipped_no_price: int
    skipped_no_indicator: int
    alert_count: int
    holding_check_ids: list[int]


def _grade_for_score(score: Decimal | None) -> str:
    if score is None:
        return "D"
    if score >= Decimal("85"):
        return "S"
    if score >= Decimal("70"):
        return "A"
    if score >= Decimal("55"):
        return "B"
    if score >= Decimal("40"):
        return "C"
    return "D"


def _decision_from_grade(grade: str) -> str:
    return {
        "S": DECISION_HOLD,
        "A": DECISION_HOLD,
        "B": DECISION_WATCH,
        "C": DECISION_REDUCE,
        "D": DECISION_SELL_REVIEW,
    }.get(grade, DECISION_SELL_REVIEW)


_DECISION_LABEL_KR = {
    DECISION_HOLD: "보유 유지",
    DECISION_WATCH: "관찰 필요",
    DECISION_REDUCE: "비중 축소 검토",
    DECISION_SELL_REVIEW: "매도 검토",
}

_RISK_FLAG_LABEL_KR = {
    RISK_FLAG_SCORE_DROP: "점수 급락",
    RISK_FLAG_MA20_BREAKDOWN: "20일선 이탈",
    RISK_FLAG_STOP_LOSS_NEAR: "손절 근접",
    "LOW_TECHNICAL_SCORE": "기술 점수 낮음",
}


def _decimal_to_str(value: Decimal | None) -> str | None:
    return str(value) if value is not None else None


def _serialize_indicator(indicator: StockIndicator) -> dict[str, Any]:
    return {
        "date": indicator.date.isoformat(),
        "ma5": _decimal_to_str(indicator.ma5),
        "ma20": _decimal_to_str(indicator.ma20),
        "ma60": _decimal_to_str(indicator.ma60),
        "ma120": _decimal_to_str(indicator.ma120),
        "rsi14": _decimal_to_str(indicator.rsi14),
        "macd": _decimal_to_str(indicator.macd),
        "macd_signal": _decimal_to_str(indicator.macd_signal),
        "volume_ratio_20d": _decimal_to_str(indicator.volume_ratio_20d),
        "breakout_20d": indicator.breakout_20d,
        "breakout_60d": indicator.breakout_60d,
        "ma_alignment": indicator.ma_alignment,
        "technical_score": _decimal_to_str(indicator.technical_score),
    }


def _serialize_price(price: DailyPrice) -> dict[str, Any]:
    return {
        "date": price.date.isoformat(),
        "open": _decimal_to_str(price.open),
        "high": _decimal_to_str(price.high),
        "low": _decimal_to_str(price.low),
        "close": _decimal_to_str(price.close),
        "volume": price.volume,
        "trading_value": _decimal_to_str(price.trading_value),
    }


def _build_reason(
    *,
    decision: str,
    return_rate: Decimal | None,
    total_score: Decimal,
    risk_flags: list[str],
) -> str:
    label = _DECISION_LABEL_KR[decision]
    return_text = (
        f"수익률 {return_rate:+.2f}%" if return_rate is not None else "수익률 N/A"
    )
    base = f"{label} ({return_text}, 종합점수 {total_score})"
    if not risk_flags:
        return base
    risk_text = ", ".join(
        _RISK_FLAG_LABEL_KR.get(flag, flag) for flag in risk_flags
    )
    return f"{base} · 위험: {risk_text}"


def _compute_return_rate(
    current_price: Decimal,
    avg_buy_price: Decimal | None,
) -> Decimal | None:
    if avg_buy_price is None or avg_buy_price == 0:
        return None
    raw = (current_price - avg_buy_price) / avg_buy_price * Decimal("100")
    return raw.quantize(_RETURN_RATE_QUANT, rounding=ROUND_HALF_UP)


def _serialize_risk_summary(assessment: RiskAssessment) -> dict[str, Any]:
    return {
        "level": assessment.risk_level,
        "flags": list(assessment.risk_flags),
        "penalty": str(assessment.risk_penalty),
    }


def _serialize_risk_details(assessment: RiskAssessment) -> dict[str, Any]:
    return {
        **assessment.details,
        "alerts": list(assessment.risk_flags),
        "risk_penalty": str(assessment.risk_penalty),
        "risk_level": assessment.risk_level,
    }


class HoldingCheckEngine:
    PHASE_TAG = "5-3"

    def __init__(
        self,
        *,
        scoring_engine: ScoringEngine,
        risk_engine: RiskEngine,
        holding_repository: HoldingRepository,
        daily_price_repository: DailyPriceRepository,
        indicator_repository: StockIndicatorRepository,
        snapshot_repository: DataSnapshotRepository,
        holding_check_repository: HoldingCheckRepository,
        decision_log_repository: DecisionLogRepository,
    ) -> None:
        self._scoring_engine = scoring_engine
        self._risk_engine = risk_engine
        self._holding_repository = holding_repository
        self._daily_price_repository = daily_price_repository
        self._indicator_repository = indicator_repository
        self._snapshot_repository = snapshot_repository
        self._holding_check_repository = holding_check_repository
        self._decision_log_repository = decision_log_repository

    def run(
        self,
        *,
        check_date: date,
        check_type: str,
    ) -> HoldingCheckResult:
        if check_type not in _VALID_CHECK_TYPES:
            raise ValueError(
                f"check_type must be one of {sorted(_VALID_CHECK_TYPES)}, "
                f"got {check_type!r}",
            )

        started_at = datetime.now(UTC)
        active_holdings = list(self._holding_repository.list_active())

        saved_ids: list[int] = []
        skipped_no_price = 0
        skipped_no_indicator = 0
        alert_count = 0

        for holding in active_holdings:
            price = self._daily_price_repository.get_latest_by_symbol(holding.symbol)
            if price is None:
                skipped_no_price += 1
                continue
            indicator = self._indicator_repository.get_latest_by_symbol(holding.symbol)
            if indicator is None:
                skipped_no_indicator += 1
                continue

            check, was_alert = self._evaluate_and_persist(
                holding=holding,
                price=price,
                indicator=indicator,
                check_date=check_date,
                check_type=check_type,
                started_at=started_at,
            )
            saved_ids.append(check.id)
            if was_alert:
                alert_count += 1

        return HoldingCheckResult(
            check_date=check_date,
            check_type=check_type,
            saved_count=len(saved_ids),
            skipped_no_price=skipped_no_price,
            skipped_no_indicator=skipped_no_indicator,
            alert_count=alert_count,
            holding_check_ids=saved_ids,
        )

    def _evaluate_and_persist(
        self,
        *,
        holding: Holding,
        price: DailyPrice,
        indicator: StockIndicator,
        check_date: date,
        check_type: str,
        started_at: datetime,
    ) -> tuple[HoldingCheck, bool]:
        current_price = price.close
        return_rate = _compute_return_rate(current_price, holding.avg_buy_price)

        # Pass 1: weighted total without risk penalty (ScoringEngine treats
        # risk_penalty=None as 0).
        weighted_only = self._scoring_engine.score_holding(
            HoldingScoreInputs(technical_score=indicator.technical_score),
        )

        previous_check = self._holding_check_repository.find_previous_for_symbol(
            holding.symbol,
            before_date=check_date,
            before_type=check_type,
        )

        # Pass 2: RiskEngine consumes pre-penalty current_total_score.
        assessment = self._risk_engine.evaluate_holding(
            technical_score=indicator.technical_score,
            current_total_score=weighted_only.total_score,
            previous_total_score=(
                previous_check.total_score if previous_check is not None else None
            ),
            current_price=current_price,
            ma20=indicator.ma20,
            return_rate=return_rate,
        )

        # Pass 3: final scoring with risk_penalty applied.
        final_score = self._scoring_engine.score_holding(
            HoldingScoreInputs(
                technical_score=indicator.technical_score,
                risk_penalty=assessment.risk_penalty,
            ),
        )

        grade = _grade_for_score(final_score.total_score)
        decision = _decision_from_grade(grade)
        reason = _build_reason(
            decision=decision,
            return_rate=return_rate,
            total_score=final_score.total_score,
            risk_flags=assessment.risk_flags,
        )

        snapshot = self._snapshot_repository.add(
            DataSnapshot(
                snapshot_time=started_at,
                symbol=holding.symbol,
                snapshot_type=_SNAPSHOT_TYPE_HOLDING_CHECK,
                price_data_json=_serialize_price(price),
                indicator_data_json=_serialize_indicator(indicator),
                news_data_json=None,
                market_context_json={
                    "check_date": check_date.isoformat(),
                    "check_type": check_type,
                    "phase": self.PHASE_TAG,
                    "risk_summary": _serialize_risk_summary(assessment),
                },
            ),
        )

        check = self._holding_check_repository.upsert(
            check_date=check_date,
            check_type=check_type,
            symbol=holding.symbol,
            current_price=current_price,
            avg_buy_price=holding.avg_buy_price,
            return_rate=return_rate,
            technical_score=indicator.technical_score,
            news_score=None,
            earnings_score=None,
            ai_score=None,
            risk_score=assessment.risk_penalty,
            total_score=final_score.total_score,
            grade=grade,
            decision=decision,
            reason=reason,
            alert=bool(assessment.risk_flags),
            snapshot_id=snapshot.snapshot_id,
        )

        rule_result = {
            "weighted_components": {
                name: str(value)
                for name, value in final_score.weighted_components.items()
            },
            "raw_total": str(final_score.raw_total),
            "total_score": str(final_score.total_score),
            "risk_penalty": str(final_score.risk_penalty),
            "placeholder_components": ["news", "earnings", "ai"],
            "return_rate": _decimal_to_str(return_rate),
            "current_price": _decimal_to_str(current_price),
            "avg_buy_price": _decimal_to_str(holding.avg_buy_price),
            "grade": grade,
        }

        self._decision_log_repository.add(
            DecisionLog(
                decision_type=_DECISION_TYPE_HOLDING,
                symbol=holding.symbol,
                input_snapshot_id=snapshot.snapshot_id,
                rule_result_json=rule_result,
                ai_result_json=None,
                risk_result_json=_serialize_risk_details(assessment),
                final_decision=decision,
                reason=reason,
            ),
        )

        return check, bool(assessment.risk_flags)
