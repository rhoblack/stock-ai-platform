"""RecommendationEngine v0.1 — Phase 5-3 watch-candidate generator.

Reads the MARKET_CAP_TOP_500 (or caller-supplied) universe membership, pulls
the latest stock_indicators row per member symbol, evaluates risk via
``RiskEngine.evaluate_recommendation`` and scores via
``ScoringEngine.score_new_recommendation`` (with risk_penalty fed back in),
and persists the TOP-N candidates plus their reasoning to
``recommendation_runs``, ``recommendations``, ``data_snapshots``, and
``decision_logs``.

Boundary rules (Phase 5-3):
    * No KIS API call.
    * No technical indicator recomputation (read-only against ``stock_indicators``).
    * No holding-check logic.
    * No Telegram, AI/LLM, or order placement.
    * Reason text stays factual ("관찰 후보 …"); no buy directive language.
    * RiskEngine is observational; it produces ``risk_penalty`` and ``risk_level``
      that flow into scoring/snapshot/decision_log but never block or execute.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any

from app.analysis.score_producers import (
    DummyScoreProducer,
    RecommendationComponentScores,
)
from app.data.repositories.decision_logs import DecisionLogRepository
from app.data.repositories.recommendations import (
    RecommendationRepository,
    RecommendationRunRepository,
)
from app.data.repositories.snapshots import DataSnapshotRepository
from app.data.repositories.stock_indicators import StockIndicatorRepository
from app.data.repositories.stock_universes import (
    StockUniverseMemberRepository,
    StockUniverseRepository,
)
from app.data.repositories.stocks import StockRepository
from app.db.models import (
    DataSnapshot,
    DecisionLog,
    Recommendation,
    RecommendationRun,
    Stock,
    StockIndicator,
)
from app.decision.risk_engine import RiskAssessment, RiskEngine
from app.decision.scoring_engine import (
    NewRecommendationScoreInputs,
    ScoreBreakdown,
    ScoringEngine,
)


_RUN_STATUS_RUNNING = "RUNNING"
_RUN_STATUS_SUCCESS = "SUCCESS"
_RUN_STATUS_EMPTY = "EMPTY"

_SNAPSHOT_TYPE_RECOMMENDATION = "RECOMMENDATION"
_DECISION_TYPE_RECOMMENDATION = "RECOMMENDATION"


@dataclass(frozen=True)
class _Candidate:
    stock: Stock
    indicator: StockIndicator
    components: RecommendationComponentScores
    score: ScoreBreakdown
    risk: RiskAssessment


@dataclass(frozen=True)
class RecommendationRunResult:
    run_id: int
    run_date: date
    status: str
    candidate_count: int
    saved_count: int
    skipped_no_indicator: int
    skipped_no_stock_master: int


def _grade_for_score(score: Decimal) -> str:
    if score >= Decimal("85"):
        return "S"
    if score >= Decimal("70"):
        return "A"
    if score >= Decimal("55"):
        return "B"
    if score >= Decimal("40"):
        return "C"
    return "D"


def _watch_candidate_reason(indicator: StockIndicator) -> str:
    parts: list[str] = ["관찰 후보"]
    if indicator.technical_score is not None:
        parts.append(f"기술점수 {indicator.technical_score}")
    if indicator.ma_alignment:
        parts.append(f"MA정렬 {indicator.ma_alignment}")
    if indicator.volume_ratio_20d is not None:
        parts.append(f"거래량비 {indicator.volume_ratio_20d}")
    return " · ".join(parts)


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


def _serialize_score_components(score: ScoreBreakdown) -> dict[str, Any]:
    return {
        "weighted_components": {
            name: str(value) for name, value in score.weighted_components.items()
        },
        "raw_total": str(score.raw_total),
        "total_score": str(score.total_score),
        "risk_penalty": str(score.risk_penalty),
    }


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


class RecommendationEngine:
    DEFAULT_UNIVERSE_NAME = "MARKET_CAP_TOP_500"
    DEFAULT_TOP_N = 5
    PHASE_TAG = "5-3"

    def __init__(
        self,
        *,
        scoring_engine: ScoringEngine,
        risk_engine: RiskEngine,
        universe_repository: StockUniverseRepository,
        member_repository: StockUniverseMemberRepository,
        stock_repository: StockRepository,
        indicator_repository: StockIndicatorRepository,
        snapshot_repository: DataSnapshotRepository,
        run_repository: RecommendationRunRepository,
        recommendation_repository: RecommendationRepository,
        decision_log_repository: DecisionLogRepository,
        score_producer: DummyScoreProducer | None = None,
    ) -> None:
        self._scoring_engine = scoring_engine
        self._risk_engine = risk_engine
        self._score_producer = score_producer or DummyScoreProducer()
        self._universe_repository = universe_repository
        self._member_repository = member_repository
        self._stock_repository = stock_repository
        self._indicator_repository = indicator_repository
        self._snapshot_repository = snapshot_repository
        self._run_repository = run_repository
        self._recommendation_repository = recommendation_repository
        self._decision_log_repository = decision_log_repository

    def generate(
        self,
        *,
        run_date: date,
        universe_name: str | None = None,
        top_n: int = DEFAULT_TOP_N,
    ) -> RecommendationRunResult:
        started_at = datetime.now(UTC)
        target_universe_name = universe_name or self.DEFAULT_UNIVERSE_NAME

        run = self._run_repository.add(
            RecommendationRun(
                run_date=run_date,
                started_at=started_at,
                status=_RUN_STATUS_RUNNING,
                market_summary=None,
                telegram_sent=False,
            ),
        )

        universe = self._universe_repository.get_by_name(target_universe_name)
        members = (
            self._member_repository.list_by_universe(universe.universe_id)
            if universe is not None
            else []
        )

        candidates: list[_Candidate] = []
        skipped_no_indicator = 0
        skipped_no_stock = 0
        for member in members:
            stock = self._stock_repository.get_by_symbol(member.symbol)
            if stock is None:
                skipped_no_stock += 1
                continue
            indicator = self._indicator_repository.get_latest_by_symbol(member.symbol)
            if indicator is None:
                skipped_no_indicator += 1
                continue

            risk = self._risk_engine.evaluate_recommendation(
                technical_score=indicator.technical_score,
                ma_alignment=indicator.ma_alignment,
                volume_ratio_20d=indicator.volume_ratio_20d,
            )
            components = self._score_producer.score_recommendation(
                stock=stock,
                indicator=indicator,
            )
            score = self._scoring_engine.score_new_recommendation(
                NewRecommendationScoreInputs(
                    technical_score=indicator.technical_score,
                    news_score=components.news_score,
                    supply_score=components.supply_score,
                    fundamental_score=components.fundamental_score,
                    ai_score=components.ai_score,
                    risk_penalty=risk.risk_penalty,
                ),
            )
            candidates.append(
                _Candidate(
                    stock=stock,
                    indicator=indicator,
                    components=components,
                    score=score,
                    risk=risk,
                ),
            )

        # Stable deterministic ordering: secondary asc by symbol, primary desc by score.
        candidates.sort(key=lambda c: c.stock.symbol)
        candidates.sort(key=lambda c: c.score.total_score, reverse=True)
        top = candidates[: max(top_n, 0)]

        for rank, candidate in enumerate(top, start=1):
            self._persist_candidate(
                run=run,
                rank=rank,
                candidate=candidate,
                run_date=run_date,
                started_at=started_at,
                universe_name=target_universe_name,
            )

        run.finished_at = datetime.now(UTC)
        run.status = _RUN_STATUS_SUCCESS if top else _RUN_STATUS_EMPTY
        run.market_summary = {
            "universe": target_universe_name,
            "universe_found": universe is not None,
            "member_count": len(members),
            "candidate_count": len(candidates),
            "saved_count": len(top),
            "skipped_no_indicator": skipped_no_indicator,
            "skipped_no_stock_master": skipped_no_stock,
            "phase": self.PHASE_TAG,
            "score_components": ["news", "supply", "fundamental", "ai"],
            "score_producer": "DummyScoreProducer",
        }
        self._run_repository.session.flush()

        return RecommendationRunResult(
            run_id=run.run_id,
            run_date=run_date,
            status=run.status,
            candidate_count=len(candidates),
            saved_count=len(top),
            skipped_no_indicator=skipped_no_indicator,
            skipped_no_stock_master=skipped_no_stock,
        )

    def _persist_candidate(
        self,
        *,
        run: RecommendationRun,
        rank: int,
        candidate: _Candidate,
        run_date: date,
        started_at: datetime,
        universe_name: str,
    ) -> None:
        snapshot = self._snapshot_repository.add(
            DataSnapshot(
                snapshot_time=started_at,
                symbol=candidate.stock.symbol,
                snapshot_type=_SNAPSHOT_TYPE_RECOMMENDATION,
                price_data_json=None,
                indicator_data_json=_serialize_indicator(candidate.indicator),
                news_data_json=None,
                market_context_json={
                    "universe": universe_name,
                    "run_date": run_date.isoformat(),
                    "run_id": run.run_id,
                    "phase": self.PHASE_TAG,
                    "component_score_metadata": candidate.components.metadata,
                    "risk_summary": _serialize_risk_summary(candidate.risk),
                },
            ),
        )

        reason = _watch_candidate_reason(candidate.indicator)
        grade = _grade_for_score(candidate.score.total_score)

        self._recommendation_repository.add(
            Recommendation(
                run_id=run.run_id,
                rank=rank,
                market=candidate.stock.market,
                symbol=candidate.stock.symbol,
                name=candidate.stock.name,
                grade=grade,
                total_score=candidate.score.total_score,
                technical_score=candidate.indicator.technical_score,
                news_score=candidate.components.news_score,
                supply_score=candidate.components.supply_score,
                fundamental_score=candidate.components.fundamental_score,
                ai_score=candidate.components.ai_score,
                risk_score=candidate.risk.risk_penalty,
                reason=reason,
                risk_note=(
                    "Phase 5-3: dummy/rule-based component scores; "
                    f"risk_level={candidate.risk.risk_level}"
                ),
                watch_condition=None,
                invalid_condition=None,
                snapshot_id=snapshot.snapshot_id,
            ),
        )

        self._decision_log_repository.add(
            DecisionLog(
                decision_type=_DECISION_TYPE_RECOMMENDATION,
                symbol=candidate.stock.symbol,
                input_snapshot_id=snapshot.snapshot_id,
                rule_result_json={
                    **_serialize_score_components(candidate.score),
                    "component_scores": {
                        "news": str(candidate.components.news_score),
                        "supply": str(candidate.components.supply_score),
                        "fundamental": str(candidate.components.fundamental_score),
                        "ai": str(candidate.components.ai_score),
                    },
                    "score_producer": candidate.components.metadata,
                },
                ai_result_json=None,
                risk_result_json=_serialize_risk_details(candidate.risk),
                final_decision=f"WATCH_CANDIDATE_RANK_{rank}",
                reason=reason,
            ),
        )
