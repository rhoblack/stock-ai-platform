"""Scheduler job wrapper + 6 v0.1 job skeletons.

Boundary rules (Phase 8):
    * No real KIS API calls inside the wrapper or job functions.
    * No real Telegram dispatch — that wiring is left for a follow-up Phase.
    * No order placement / auto-trading.
    * The wrapper persists every job invocation to ``job_runs`` regardless of
      success / partial / failure, so the dashboard `/api/jobs` and operator
      retro tooling can see the full timeline.
    * Jobs that have a backing service (TechnicalIndicatorService,
      RecommendationEngine, HoldingCheckEngine) call it. KIS data collection
      is wired through read-only collectors and remains fake/mock-injectable in
      tests.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from typing import Any, Callable
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session, sessionmaker

from app.analysis.indicator_service import TechnicalIndicatorService
from app.analysis.technical_analyzer import TechnicalAnalyzer
from app.config.settings import get_settings
from app.data.collectors import (
    DailyPriceCollector,
    KisClient,
    MarketCapRankingCollector,
)
from app.data.interfaces import DataProviderInterface
from app.data.repositories.daily_prices import DailyPriceRepository
from app.data.repositories.decision_logs import DecisionLogRepository
from app.data.repositories.holdings import HoldingRepository
from app.data.repositories.holding_checks import HoldingCheckRepository
from app.data.repositories.job_runs import JobRunRepository
from app.data.repositories.market_cap_rankings import MarketCapRankingRepository
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
    HoldingRiskAlertDispatcher,
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


def _build_holding_risk_alert_dispatcher(
    session: Session,
    *,
    notifier: TelegramNotifier,
) -> HoldingRiskAlertDispatcher:
    return HoldingRiskAlertDispatcher(
        report_generator=ReportGenerator(),
        notification_service=NotificationService(
            notifier=notifier,
            log_repository=NotificationLogRepository(session),
        ),
        holding_check_repository=HoldingCheckRepository(session),
        snapshot_repository=DataSnapshotRepository(session),
        log_repository=NotificationLogRepository(session),
    )


def _serialize_quality_issues(issues) -> list[dict[str, Any]]:
    return [
        {
            "code": issue.code,
            "message": issue.message,
            "symbol": issue.symbol,
            "target_date": (
                issue.target_date.isoformat()
                if issue.target_date is not None
                else None
            ),
        }
        for issue in issues
    ]


def _resolve_data_provider(session: Session) -> tuple[DataProviderInterface, bool]:
    override = session.info.get("data_provider")
    if override is not None:
        return override, False
    return KisClient(settings=_resolve_settings(session)), True


def _market_close_job_config(session: Session) -> dict[str, Any]:
    settings = _resolve_settings(session)
    override = session.info.get("market_close_config", {})
    target_date = override.get("target_date") or _today_in_default_timezone()
    lookback_days = int(
        override.get("lookback_days", settings.daily_price_lookback_days),
    )
    if lookback_days < 1:
        lookback_days = 1
    return {
        "target_date": target_date,
        "market": override.get("market", settings.collect_market),
        "limit": int(override.get("limit", settings.market_cap_limit)),
        "universe_name": override.get(
            "universe_name",
            settings.market_cap_universe_name,
        ),
        "start_date": override.get(
            "start_date",
            target_date - timedelta(days=lookback_days - 1),
        ),
        "end_date": override.get("end_date", target_date),
        "batch_size": max(
            int(override.get("batch_size", settings.daily_price_batch_size)),
            1,
        ),
        "lookback_days": lookback_days,
    }


def _chunks(values: list[str], size: int) -> list[list[str]]:
    return [values[index:index + size] for index in range(0, len(values), size)]


def _indicator_job_config(session: Session) -> dict[str, Any]:
    settings = _resolve_settings(session)
    override = session.info.get("indicator_config", {})
    lookback_days = int(
        override.get("lookback_days", settings.indicator_lookback_days),
    )
    if lookback_days < 1:
        lookback_days = 1
    return {
        "universe_name": override.get(
            "universe_name",
            settings.indicator_universe_name,
        ),
        "lookback_days": lookback_days,
        "batch_size": max(
            int(override.get("batch_size", settings.indicator_batch_size)),
            1,
        ),
    }


# ---------- 18:00 collect_market_close_data ----------

def collect_market_close_data(session: Session) -> JobResult:
    """Collect market-cap rankings and daily prices through data collectors.

    Tests inject ``session.info["data_provider"]`` with a fake provider. In
    normal runtime, this builds the read-only KIS client from settings.
    """
    config = _market_close_job_config(session)
    target_date = config["target_date"]
    market = config["market"]
    limit = config["limit"]
    universe_name = config["universe_name"]
    start_date = config["start_date"]
    end_date = config["end_date"]
    batch_size = config["batch_size"]

    provider, should_close_provider = _resolve_data_provider(session)
    try:
        market_collector = MarketCapRankingCollector(
            client=provider,
            ranking_repository=MarketCapRankingRepository(session),
            stock_repository=StockRepository(session),
            universe_repository=StockUniverseRepository(session),
            member_repository=StockUniverseMemberRepository(session),
        )
        try:
            ranking_result = market_collector.collect(
                market=market,
                ranking_date=target_date,
                limit=limit,
                universe_name=universe_name,
            )
        except Exception as exc:  # noqa: BLE001 - vendor/normalizer failures
            return JobResult(
                status=JOB_STATUS_FAILED,
                summary={
                    "phase": "8-wired",
                    "market": market,
                    "market_cap_limit": limit,
                    "target_date": target_date.isoformat(),
                    "universe": universe_name,
                    "lookback_days": config["lookback_days"],
                    "batch_size": batch_size,
                    "market_cap_status": "FAILED",
                    "daily_price_status": "SKIPPED",
                    "failure_count": 1,
                    "failures": [
                        {
                            "stage": "market_cap_rankings",
                            "error_type": type(exc).__name__,
                            "message": str(exc),
                        },
                    ],
                },
                error_message=f"market cap collection failed: {exc}",
            )

        members = StockUniverseMemberRepository(session).list_by_universe(
            ranking_result.universe_id,
        )
        symbols = [member.symbol for member in members]

        daily_collector = DailyPriceCollector(
            client=provider,
            repository=DailyPriceRepository(session),
        )
        daily_results = []
        failures = []
        for batch_index, batch_symbols in enumerate(_chunks(symbols, batch_size), start=1):
            logger.info(
                "collecting daily prices batch %s (%s symbols)",
                batch_index,
                len(batch_symbols),
            )
            for symbol in batch_symbols:
                try:
                    result = daily_collector.collect(
                        symbol=symbol,
                        start_date=start_date,
                        end_date=end_date,
                    )
                except Exception as exc:  # noqa: BLE001 - keep collecting others
                    failures.append(
                        {
                            "stage": "daily_prices",
                            "symbol": symbol,
                            "error_type": type(exc).__name__,
                            "message": str(exc),
                        },
                    )
                    continue

                daily_results.append(
                    {
                        "symbol": result.symbol,
                        "saved_count": result.saved_count,
                        "quality_issues": _serialize_quality_issues(
                            result.quality_issues,
                        ),
                    },
                )
        success_count = len(daily_results)
        failure_count = len(failures)
        if symbols and success_count == 0:
            status = JOB_STATUS_FAILED
            error_message = "all daily price collections failed"
        elif failure_count > 0:
            status = JOB_STATUS_PARTIAL
            error_message = f"{failure_count} daily price collections failed"
        else:
            status = JOB_STATUS_SUCCESS
            error_message = None

        return JobResult(
            status=status,
            summary={
                "phase": "8-wired",
                "market": market,
                "market_cap_limit": limit,
                "target_date": target_date.isoformat(),
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat(),
                "lookback_days": config["lookback_days"],
                "batch_size": batch_size,
                "universe": universe_name,
                "universe_id": ranking_result.universe_id,
                "market_cap_status": "SUCCESS",
                "market_cap_saved_rankings": ranking_result.saved_rankings,
                "market_cap_new_stocks": ranking_result.new_stocks,
                "market_cap_new_universe_members": (
                    ranking_result.new_universe_members
                ),
                "market_cap_quality_issues": _serialize_quality_issues(
                    ranking_result.quality_issues,
                ),
                "daily_price_status": status,
                "symbols_count": len(symbols),
                "daily_success_count": success_count,
                "daily_failure_count": failure_count,
                "daily_saved_rows": sum(r["saved_count"] for r in daily_results),
                "daily_results": daily_results,
                "failures": failures,
            },
            error_message=error_message,
        )
    finally:
        if should_close_provider and hasattr(provider, "close"):
            provider.close()


# ---------- 18:30 calculate_technical_indicators ----------

def calculate_technical_indicators(session: Session) -> JobResult:
    """Compute indicators for every active universe member that has prices."""
    config = _indicator_job_config(session)
    universe_name = config["universe_name"]
    lookback_days = config["lookback_days"]
    batch_size = config["batch_size"]

    universe = StockUniverseRepository(session).get_by_name(universe_name)
    if universe is None:
        return JobResult(
            status=JOB_STATUS_SUCCESS,
            summary={
                "phase": "8",
                "skipped": True,
                "reason": f"{universe_name} universe missing",
                "universe": universe_name,
                "lookback_days": lookback_days,
                "batch_size": batch_size,
                "members_count": 0,
                "snapshots_saved": 0,
                "success_count": 0,
                "skipped_no_prices": 0,
                "failure_count": 0,
            },
        )

    members = StockUniverseMemberRepository(session).list_by_universe(
        universe.universe_id,
    )
    symbols = [member.symbol for member in members]
    service = TechnicalIndicatorService(
        daily_price_repository=DailyPriceRepository(session),
        indicator_repository=StockIndicatorRepository(session),
        analyzer=session.info.get("technical_analyzer") or TechnicalAnalyzer(),
    )

    successes = []
    skipped = []
    failures = []
    for batch_index, batch_symbols in enumerate(_chunks(symbols, batch_size), start=1):
        logger.info(
            "calculating technical indicators batch %s (%s symbols)",
            batch_index,
            len(batch_symbols),
        )
        for symbol in batch_symbols:
            try:
                snapshot = service.analyze_and_store(
                    symbol,
                    lookback_days=lookback_days,
                )
            except Exception as exc:  # noqa: BLE001 - isolate symbol failures
                failures.append(
                    {
                        "symbol": symbol,
                        "error_type": type(exc).__name__,
                        "message": str(exc),
                    },
                )
                continue

            if snapshot is None:
                skipped.append(
                    {
                        "symbol": symbol,
                        "reason": "NO_DAILY_PRICES",
                    },
                )
                continue

            successes.append(
                {
                    "symbol": snapshot.symbol,
                    "indicator_date": snapshot.date.isoformat(),
                    "technical_score": str(snapshot.technical_score),
                },
            )

    success_count = len(successes)
    skipped_count = len(skipped)
    failure_count = len(failures)
    if failure_count > 0 and success_count == 0:
        status = JOB_STATUS_FAILED
        error_message = "all technical indicator calculations failed"
    elif failure_count > 0 or skipped_count > 0:
        status = JOB_STATUS_PARTIAL
        error_message = None
        if failure_count > 0:
            error_message = f"{failure_count} technical indicator calculations failed"
    else:
        status = JOB_STATUS_SUCCESS
        error_message = None

    return JobResult(
        status=status,
        summary={
            "phase": "8",
            "universe": universe_name,
            "universe_id": universe.universe_id,
            "lookback_days": lookback_days,
            "batch_size": batch_size,
            "members_count": len(symbols),
            "snapshots_saved": success_count,
            "success_count": success_count,
            "skipped_no_prices": skipped_count,
            "failure_count": failure_count,
            "successes": successes,
            "skipped": skipped,
            "failures": failures,
        },
        error_message=error_message,
    )


# ---------- 06:00 send_recommendation_report ----------

def send_recommendation_report(session: Session) -> JobResult:
    """Dispatch the latest recommendation run report via Telegram.

    The notifier respects ``settings.telegram_enabled``. When False (default
    for v0.1 / tests) the dispatch records a DRY_RUN notification_logs row
    without contacting telegram.org, so this job is safe to run automatically.
    """
    job_run_id = session.info.get("job_run_id")
    settings = _resolve_settings(session)

    run = RecommendationRunRepository(session).latest()
    if run is None:
        return JobResult(
            status=JOB_STATUS_SUCCESS,
            summary={
                "phase": "8-followup",
                "run_id": None,
                "run_date": None,
                "notification_status": "NO_DATA",
                "telegram_sent": False,
                "dry_run": False,
                "telegram_sent_flag_updated": False,
                "notification_log_id": None,
                "recommendation_count": 0,
                "message_length": 0,
            },
        )

    notifier = TelegramNotifier(settings=settings)
    try:
        dispatcher = _build_recommendation_dispatcher(session, notifier=notifier)
        dispatch = dispatcher.dispatch(
            run_id=run.run_id,
            related_job_id=job_run_id,
        )
    finally:
        notifier.close()

    if dispatch.notification.status in _DISPATCHED_NOTIFICATION_STATUSES:
        job_status = JOB_STATUS_SUCCESS
    else:
        job_status = JOB_STATUS_PARTIAL

    return JobResult(
        status=job_status,
        summary={
            "phase": "8-followup",
            "run_id": run.run_id,
            "run_date": run.run_date.isoformat(),
            "recommendation_count": dispatch.recommendation_count,
            "telegram_sent": dispatch.notification.sent,
            "dry_run": dispatch.notification.status == "DRY_RUN",
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
        
        alert_dispatcher = _build_holding_risk_alert_dispatcher(session, notifier=notifier)
        alert_count = alert_dispatcher.dispatch(
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
            "alert_sent_count": alert_count,
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
