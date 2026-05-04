"""Scheduler job wrapper + 6 v0.1 job skeletons.

Boundary rules (Phase 8):
    * No real KIS API calls inside the wrapper or job functions.
    * No real Telegram dispatch — that wiring is left for a follow-up Phase.
    * No order placement / auto-trading.
    * The wrapper persists every job invocation to ``job_runs`` regardless of
      success / partial / failure, so the dashboard `/api/jobs` and operator
      retro tooling can see the full timeline.
    * Jobs that have a backing service (TechnicalIndicatorService,
      RecommendationEngine, HoldingCheckEngine) call it. Jobs that don't yet
      (KIS data collection, recommendation result update) return a documented
      placeholder summary with ``placeholder=True``.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import UTC, date, datetime
from typing import Any, Callable
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session, sessionmaker

from app.analysis.indicator_service import TechnicalIndicatorService
from app.analysis.technical_analyzer import TechnicalAnalyzer
from app.config.settings import get_settings
from app.data.repositories.daily_prices import DailyPriceRepository
from app.data.repositories.decision_logs import DecisionLogRepository
from app.data.repositories.holdings import HoldingRepository
from app.data.repositories.holding_checks import HoldingCheckRepository
from app.data.repositories.job_runs import JobRunRepository
from app.data.repositories.notification_logs import NotificationLogRepository
from app.data.repositories.recommendations import (
    RecommendationRepository,
    RecommendationResultRepository,
    RecommendationRunRepository,
)
from app.data.repositories.snapshots import DataSnapshotRepository
from app.data.repositories.stock_indicators import StockIndicatorRepository
from app.data.repositories.stock_universes import (
    StockUniverseMemberRepository,
    StockUniverseRepository,
)
from app.data.repositories.stocks import StockRepository
from app.db.models import JobRun
from app.decision.holding_check_engine import (
    CHECK_TYPE_POST_MARKET,
    CHECK_TYPE_PRE_MARKET,
    HoldingCheckEngine,
)
from app.decision.recommendation_engine import RecommendationEngine
from app.decision.recommendation_result_service import RecommendationResultService
from app.decision.risk_engine import RiskEngine
from app.decision.scoring_engine import ScoringEngine
from app.notification.dispatchers import (
    HoldingCheckReportDispatcher,
    RecommendationReportDispatcher,
)
from app.notification.notification_service import NotificationService
from app.notification.report_generator import ReportGenerator
from app.notification.telegram_notifier import TelegramNotifier


logger = logging.getLogger(__name__)


JOB_STATUS_RUNNING = "RUNNING"
JOB_STATUS_SUCCESS = "SUCCESS"
JOB_STATUS_PARTIAL = "PARTIAL"
JOB_STATUS_FAILED = "FAILED"


JOB_NAME_COLLECT_MARKET_CLOSE = "collect_market_close_data"
JOB_NAME_CALCULATE_INDICATORS = "calculate_technical_indicators"
JOB_NAME_SEND_RECOMMENDATION_REPORT = "send_recommendation_report"
JOB_NAME_PRE_MARKET_HOLDING_CHECK = "run_pre_market_holding_check"
JOB_NAME_POST_MARKET_HOLDING_CHECK = "run_post_market_holding_check"
JOB_NAME_UPDATE_RECOMMENDATION_RESULTS = "update_recommendation_results"


@dataclass(frozen=True)
class JobResult:
    """What a job function returns to the wrapper.

    ``status`` should be one of SUCCESS / PARTIAL. To signal failure, raise
    instead of returning — the wrapper records FAILED automatically.
    """

    status: str = JOB_STATUS_SUCCESS
    summary: dict[str, Any] | None = None
    error_message: str | None = None


@dataclass(frozen=True)
class JobOutcome:
    job_run_id: int
    job_name: str
    status: str
    started_at: datetime
    finished_at: datetime
    result_summary: dict[str, Any] | None
    error_message: str | None


JobFn = Callable[[Session], JobResult]


def run_job(
    *,
    session_factory: sessionmaker[Session],
    job_name: str,
    fn: JobFn,
) -> JobOutcome:
    """Run ``fn(session)`` and persist the outcome to ``job_runs``.

    Two sessions are used: one for the ``job_runs`` row (always commits) and
    one for the actual work (commits on success, rolls back on error). This
    keeps the audit log row consistent even if the job's own DB writes fail.
    """
    started_at = datetime.now(UTC)

    log_session = session_factory()
    try:
        job_run = JobRunRepository(log_session).add(
            JobRun(
                job_name=job_name,
                started_at=started_at,
                status=JOB_STATUS_RUNNING,
            ),
        )
        log_session.commit()
        job_run_id = job_run.job_id

        status: str
        summary: dict[str, Any] | None
        error: str | None

        work_session = session_factory()
        # Expose job_run_id on the session so jobs (e.g., dispatcher-using
        # ones) can pass it to NotificationService.send_telegram and link
        # notification_logs.related_job_id back to this job_runs row.
        work_session.info["job_run_id"] = job_run_id
        try:
            try:
                result = fn(work_session)
            except Exception as exc:  # noqa: BLE001 - jobs may raise anything
                logger.exception("scheduler job %s failed", job_name)
                work_session.rollback()
                status = JOB_STATUS_FAILED
                summary = None
                error = f"{type(exc).__name__}: {exc}"
            else:
                work_session.commit()
                status = result.status
                summary = result.summary
                error = result.error_message
        finally:
            work_session.close()

        finished_at = datetime.now(UTC)
        job_run.status = status
        job_run.finished_at = finished_at
        job_run.result_summary = summary
        job_run.error_message = error
        log_session.commit()
    finally:
        log_session.close()

    return JobOutcome(
        job_run_id=job_run_id,
        job_name=job_name,
        status=status,
        started_at=started_at,
        finished_at=finished_at,
        result_summary=summary,
        error_message=error,
    )


# ---------- helpers ----------

def _today_in_default_timezone() -> date:
    settings = get_settings()
    try:
        tz = ZoneInfo(settings.timezone)
    except Exception:  # noqa: BLE001 - fall back to UTC if tz name is bad
        return datetime.now(UTC).date()
    return datetime.now(tz).date()


def _build_recommendation_engine(session: Session) -> RecommendationEngine:
    return RecommendationEngine(
        scoring_engine=ScoringEngine(),
        risk_engine=RiskEngine(),
        universe_repository=StockUniverseRepository(session),
        member_repository=StockUniverseMemberRepository(session),
        stock_repository=StockRepository(session),
        indicator_repository=StockIndicatorRepository(session),
        snapshot_repository=DataSnapshotRepository(session),
        run_repository=RecommendationRunRepository(session),
        recommendation_repository=RecommendationRepository(session),
        decision_log_repository=DecisionLogRepository(session),
    )


def _build_holding_check_engine(session: Session) -> HoldingCheckEngine:
    return HoldingCheckEngine(
        scoring_engine=ScoringEngine(),
        risk_engine=RiskEngine(),
        holding_repository=HoldingRepository(session),
        daily_price_repository=DailyPriceRepository(session),
        indicator_repository=StockIndicatorRepository(session),
        snapshot_repository=DataSnapshotRepository(session),
        holding_check_repository=HoldingCheckRepository(session),
        decision_log_repository=DecisionLogRepository(session),
    )


_DISPATCHED_NOTIFICATION_STATUSES = {"SUCCESS", "DRY_RUN"}


def _resolve_settings(session: Session):
    """Resolve settings, preferring an explicit override stored on the session.

    Tests may set ``session.info['settings']`` to inject deterministic values
    (e.g., telegram_enabled=False) without depending on env / lru_cache state.
    """
    override = session.info.get("settings")
    if override is not None:
        return override
    return get_settings()


def _build_recommendation_dispatcher(
    session: Session,
    *,
    notifier: TelegramNotifier,
) -> RecommendationReportDispatcher:
    return RecommendationReportDispatcher(
        report_generator=ReportGenerator(),
        notification_service=NotificationService(
            notifier=notifier,
            log_repository=NotificationLogRepository(session),
        ),
        run_repository=RecommendationRunRepository(session),
        recommendation_repository=RecommendationRepository(session),
        snapshot_repository=DataSnapshotRepository(session),
    )


def _build_holding_check_dispatcher(
    session: Session,
    *,
    notifier: TelegramNotifier,
) -> HoldingCheckReportDispatcher:
    return HoldingCheckReportDispatcher(
        report_generator=ReportGenerator(),
        notification_service=NotificationService(
            notifier=notifier,
            log_repository=NotificationLogRepository(session),
        ),
        holding_check_repository=HoldingCheckRepository(session),
        snapshot_repository=DataSnapshotRepository(session),
    )


# ---------- 18:00 collect_market_close_data ----------

def collect_market_close_data(session: Session) -> JobResult:
    """Phase 8 placeholder for the KIS close-data ingestion job.

    Real wiring (DailyPriceCollector / MarketCapRankingCollector) is left for
    a Phase 8 follow-up so this job doesn't accidentally hit the live KIS
    service. The placeholder emits a deterministic summary so dashboards can
    render the row.
    """
    return JobResult(
        status=JOB_STATUS_SUCCESS,
        summary={
            "phase": "8",
            "placeholder": True,
            "note": "KIS data ingestion not yet wired into scheduler",
        },
    )


# ---------- 18:30 calculate_technical_indicators ----------

def calculate_technical_indicators(session: Session) -> JobResult:
    """Compute indicators for every active universe member that has prices."""
    universe = StockUniverseRepository(session).get_by_name("MARKET_CAP_TOP_500")
    if universe is None:
        return JobResult(
            status=JOB_STATUS_SUCCESS,
            summary={
                "phase": "8",
                "skipped": True,
                "reason": "MARKET_CAP_TOP_500 universe missing",
                "members_count": 0,
                "snapshots_saved": 0,
            },
        )

    members = StockUniverseMemberRepository(session).list_by_universe(
        universe.universe_id,
    )
    service = TechnicalIndicatorService(
        daily_price_repository=DailyPriceRepository(session),
        indicator_repository=StockIndicatorRepository(session),
        analyzer=TechnicalAnalyzer(),
    )
    snapshots = service.analyze_and_store_many(
        symbols=[m.symbol for m in members],
    )
    return JobResult(
        status=JOB_STATUS_SUCCESS,
        summary={
            "phase": "8",
            "members_count": len(members),
            "snapshots_saved": len(snapshots),
            "skipped_no_prices": len(members) - len(snapshots),
        },
    )


# ---------- 06:00 send_recommendation_report ----------

def send_recommendation_report(session: Session) -> JobResult:
    """Generate a recommendation run and dispatch the report via Telegram.

    The notifier respects ``settings.telegram_enabled``. When False (default
    for v0.1 / tests) the dispatch records a DRY_RUN notification_logs row
    without contacting telegram.org, so this job is safe to run automatically.
    """
    job_run_id = session.info.get("job_run_id")
    settings = _resolve_settings(session)

    engine = _build_recommendation_engine(session)
    result = engine.generate(run_date=_today_in_default_timezone())

    notifier = TelegramNotifier(settings=settings)
    try:
        dispatcher = _build_recommendation_dispatcher(session, notifier=notifier)
        dispatch = dispatcher.dispatch(
            run_id=result.run_id,
            related_job_id=job_run_id,
        )
    finally:
        notifier.close()

    if result.status == "EMPTY":
        job_status = JOB_STATUS_PARTIAL
    elif dispatch.notification.status in _DISPATCHED_NOTIFICATION_STATUSES:
        job_status = JOB_STATUS_SUCCESS
    else:
        job_status = JOB_STATUS_PARTIAL

    return JobResult(
        status=job_status,
        summary={
            "phase": "8-followup",
            "run_id": result.run_id,
            "run_date": result.run_date.isoformat(),
            "engine_status": result.status,
            "candidate_count": result.candidate_count,
            "saved_count": result.saved_count,
            "skipped_no_indicator": result.skipped_no_indicator,
            "skipped_no_stock_master": result.skipped_no_stock_master,
            "recommendation_count": dispatch.recommendation_count,
            "telegram_sent": dispatch.notification.sent,
            "telegram_sent_flag_updated": dispatch.telegram_sent_flag_updated,
            "notification_status": dispatch.notification.status,
            "notification_log_id": dispatch.notification.notification_log_id,
            "message_length": len(dispatch.message_text),
        },
    )


def _run_holding_check_job(
    session: Session,
    *,
    check_type: str,
) -> JobResult:
    job_run_id = session.info.get("job_run_id")
    settings = _resolve_settings(session)

    engine = _build_holding_check_engine(session)
    check_date = _today_in_default_timezone()
    result = engine.run(check_date=check_date, check_type=check_type)

    notifier = TelegramNotifier(settings=settings)
    try:
        dispatcher = _build_holding_check_dispatcher(session, notifier=notifier)
        dispatch = dispatcher.dispatch(
            check_date=check_date,
            check_type=check_type,
            related_job_id=job_run_id,
        )
    finally:
        notifier.close()

    has_skips = result.skipped_no_price > 0 or result.skipped_no_indicator > 0
    dispatch_ok = dispatch.notification.status in _DISPATCHED_NOTIFICATION_STATUSES
    if dispatch_ok and not has_skips:
        job_status = JOB_STATUS_SUCCESS
    else:
        job_status = JOB_STATUS_PARTIAL

    return JobResult(
        status=job_status,
        summary={
            "phase": "8-followup",
            "check_date": check_date.isoformat(),
            "check_type": check_type,
            "saved_count": result.saved_count,
            "skipped_no_price": result.skipped_no_price,
            "skipped_no_indicator": result.skipped_no_indicator,
            "alert_count": result.alert_count,
            "holding_check_count": dispatch.holding_check_count,
            "telegram_sent": dispatch.notification.sent,
            "notification_status": dispatch.notification.status,
            "notification_log_id": dispatch.notification.notification_log_id,
            "message_length": len(dispatch.message_text),
        },
    )


# ---------- 08:30 run_pre_market_holding_check ----------

def run_pre_market_holding_check(session: Session) -> JobResult:
    return _run_holding_check_job(session, check_type=CHECK_TYPE_PRE_MARKET)


# ---------- 16:30 run_post_market_holding_check ----------

def run_post_market_holding_check(session: Session) -> JobResult:
    return _run_holding_check_job(session, check_type=CHECK_TYPE_POST_MARKET)


# ---------- 17:00 update_recommendation_results ----------

def update_recommendation_results(session: Session) -> JobResult:
    """Compute 1/3/5/20-day post-recommendation returns and upsert results."""
    service = RecommendationResultService(
        recommendation_run_repository=RecommendationRunRepository(session),
        recommendation_repository=RecommendationRepository(session),
        recommendation_result_repository=RecommendationResultRepository(session),
        daily_price_repository=DailyPriceRepository(session),
    )
    as_of = _today_in_default_timezone()
    result = service.update_results(as_of=as_of)
    return JobResult(
        status=JOB_STATUS_SUCCESS,
        summary={
            "phase": "5-followup",
            "as_of": result.as_of.isoformat(),
            "processed_runs": result.processed_runs,
            "processed_recommendations": result.processed_recommendations,
            "upserted_results": result.upserted_results,
            "pending_count": result.pending_count,
            "success_count": result.success_count,
            "failed_count": result.failed_count,
            "skipped_no_reference": result.skipped_no_reference,
        },
    )


# ---------- registry for the scheduler module ----------

JOB_FUNCTIONS: dict[str, JobFn] = {
    JOB_NAME_COLLECT_MARKET_CLOSE: collect_market_close_data,
    JOB_NAME_CALCULATE_INDICATORS: calculate_technical_indicators,
    JOB_NAME_SEND_RECOMMENDATION_REPORT: send_recommendation_report,
    JOB_NAME_PRE_MARKET_HOLDING_CHECK: run_pre_market_holding_check,
    JOB_NAME_POST_MARKET_HOLDING_CHECK: run_post_market_holding_check,
    JOB_NAME_UPDATE_RECOMMENDATION_RESULTS: update_recommendation_results,
}
