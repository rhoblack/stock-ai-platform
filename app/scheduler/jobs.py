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
from app.data.repositories.report_consensus_snapshots import (
    ReportConsensusSnapshotRepository,
)
from app.data.repositories.report_score_logs import ReportScoreLogRepository
from app.data.repositories.report_signal_events import ReportSignalEventRepository
from app.data.repositories.snapshots import DataSnapshotRepository
from app.data.repositories.stock_indicators import StockIndicatorRepository
from app.data.repositories.stock_universes import (
    StockUniverseMemberRepository,
    StockUniverseRepository,
)
from app.data.repositories.stocks import StockRepository
from app.data.repositories.theme_stock_mappings import ThemeStockMappingRepository
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
JOB_NAME_UPDATE_REPORT_CONSENSUS = "update_report_consensus_snapshots"
JOB_NAME_COLLECT_NEWS = "collect_news"
JOB_NAME_COLLECT_DISCLOSURES = "collect_disclosures"


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
        daily_price_repository=DailyPriceRepository(session),
        report_consensus_repository=ReportConsensusSnapshotRepository(session),
        theme_mapping_repository=ThemeStockMappingRepository(session),
        report_signal_event_repository=ReportSignalEventRepository(session),
        report_score_log_repository=ReportScoreLogRepository(session),
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
    check_date = _today_in_default_timezone()

    active_holdings = list(HoldingRepository(session).list_active())
    if not active_holdings:
        return JobResult(
            status=JOB_STATUS_SUCCESS,
            summary={
                "phase": "8-followup",
                "check_date": check_date.isoformat(),
                "check_type": check_type,
                "checked_count": 0,
                "saved_count": 0,
                "skipped_no_price": 0,
                "skipped_no_indicator": 0,
                "alert_count": 0,
                "holding_check_count": 0,
                "alert_sent_count": 0,
                "telegram_sent": False,
                "dry_run": False,
                "notification_status": "NO_DATA",
                "notification_log_id": None,
                "message_length": 0,
            },
        )

    engine = _build_holding_check_engine(session)
    result = engine.run(check_date=check_date, check_type=check_type)

    notifier = TelegramNotifier(settings=settings)
    try:
        dispatcher = _build_holding_check_dispatcher(session, notifier=notifier)
        dispatch = dispatcher.dispatch(
            check_date=check_date,
            check_type=check_type,
            related_job_id=job_run_id,
        )

        alert_dispatcher = _build_holding_risk_alert_dispatcher(
            session, notifier=notifier,
        )
        alert_sent_count = alert_dispatcher.dispatch(
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
            "checked_count": result.saved_count,
            "saved_count": result.saved_count,
            "skipped_no_price": result.skipped_no_price,
            "skipped_no_indicator": result.skipped_no_indicator,
            "alert_count": result.alert_count,
            "holding_check_count": dispatch.holding_check_count,
            "alert_sent_count": alert_sent_count,
            "telegram_sent": dispatch.notification.sent,
            "dry_run": dispatch.notification.status == "DRY_RUN",
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
    """Compute 1/3/5/20-day post-recommendation returns and upsert results.

    JobResult.status mapping:
        * No recommendations in the lookback window  → SUCCESS, data_status=NO_DATA
        * One or more recommendations missing a reference price  → PARTIAL,
          data_status=PARTIAL (those rows are upserted as PENDING and re-checked
          on the next run)
        * Otherwise  → SUCCESS, data_status=SUCCESS
    """
    service = RecommendationResultService(
        recommendation_run_repository=RecommendationRunRepository(session),
        recommendation_repository=RecommendationRepository(session),
        recommendation_result_repository=RecommendationResultRepository(session),
        daily_price_repository=DailyPriceRepository(session),
    )
    lookback_days = service.DEFAULT_LOOKBACK_DAYS
    as_of = _today_in_default_timezone()
    result = service.update_results(as_of=as_of, lookback_days=lookback_days)

    if result.processed_recommendations == 0:
        data_status = "NO_DATA"
        job_status = JOB_STATUS_SUCCESS
        error_message = None
    elif result.skipped_no_reference > 0:
        data_status = "PARTIAL"
        job_status = JOB_STATUS_PARTIAL
        error_message = (
            f"{result.skipped_no_reference} recommendations had no reference price"
        )
    else:
        data_status = "SUCCESS"
        job_status = JOB_STATUS_SUCCESS
        error_message = None

    return JobResult(
        status=job_status,
        summary={
            "phase": "5-followup",
            "as_of": result.as_of.isoformat(),
            "lookback_days": lookback_days,
            "data_status": data_status,
            "processed_runs": result.processed_runs,
            "processed_count": result.processed_recommendations,
            "processed_recommendations": result.processed_recommendations,
            "upserted_results": result.upserted_results,
            "pending_count": result.pending_count,
            "success_count": result.success_count,
            "failed_count": result.failed_count,
            "skipped_no_reference": result.skipped_no_reference,
        },
        error_message=error_message,
    )


# ---------- 06:30 update_report_consensus_snapshots (v0.4 Phase B) ----------


DEFAULT_CONSENSUS_WINDOW_DAYS = 90


def update_report_consensus_snapshots(session: Session) -> JobResult:
    """Aggregate active COMPANY analyst reports into per-symbol consensus rows.

    For every distinct symbol that has at least one COMPANY-type report
    published within the last ``window_days`` (default 90), upsert one row in
    ``report_consensus_snapshots`` with avg/min/max target_price + the 5 rating
    counts + ``latest_published_at``. Idempotent: re-runs on the same
    ``snapshot_date`` overwrite the previous snapshot for that
    ``(symbol, snapshot_date, window_days)`` triple.

    JobResult.status mapping:
        * No active reports in the window  → SUCCESS, data_status=NO_DATA
        * Otherwise                        → SUCCESS, data_status=SUCCESS

    No KIS / Telegram / external calls. Reads `analyst_reports`, writes
    `report_consensus_snapshots`.
    """
    from decimal import Decimal as _Dec  # local alias to avoid surprise imports

    from app.data.repositories.analyst_reports import AnalystReportRepository
    from app.data.repositories.report_consensus_snapshots import (
        ReportConsensusSnapshotRepository,
    )
    from app.db.models import AnalystReport
    from sqlalchemy import select

    snapshot_date = _today_in_default_timezone()
    window_days = DEFAULT_CONSENSUS_WINDOW_DAYS
    cutoff = snapshot_date - timedelta(days=window_days)

    # Pull all active COMPANY reports within the window in one query.
    statement = (
        select(AnalystReport)
        .where(
            AnalystReport.report_type == "COMPANY",
            AnalystReport.published_at >= cutoff,
            AnalystReport.published_at <= snapshot_date,
            AnalystReport.symbol.is_not(None),
        )
        .order_by(AnalystReport.published_at.asc())
    )
    rows = list(session.execute(statement).scalars().all())

    if not rows:
        return JobResult(
            status=JOB_STATUS_SUCCESS,
            summary={
                "phase": "v0.4-B",
                "snapshot_date": snapshot_date.isoformat(),
                "window_days": window_days,
                "data_status": "NO_DATA",
                "active_reports": 0,
                "symbols_processed": 0,
                "snapshots_upserted": 0,
            },
        )

    by_symbol: dict[str, list[AnalystReport]] = {}
    for r in rows:
        by_symbol.setdefault(r.symbol, []).append(r)

    repo = ReportConsensusSnapshotRepository(session)
    snapshots_upserted = 0
    rating_to_field = {
        "STRONG_BUY": "strong_buy_count",
        "BUY": "buy_count",
        "HOLD": "hold_count",
        "SELL": "sell_count",
        "STRONG_SELL": "strong_sell_count",
    }
    for symbol, reports in by_symbol.items():
        targets = [r.target_price for r in reports if r.target_price is not None]
        rating_counts = {f: 0 for f in rating_to_field.values()}
        for r in reports:
            field = rating_to_field.get(r.normalized_rating or "")
            if field is not None:
                rating_counts[field] += 1
        latest_pub = max(r.published_at for r in reports)

        avg_target = (
            (sum(targets, _Dec("0")) / _Dec(len(targets))) if targets else None
        )
        repo.upsert_by_symbol_date_window(
            symbol=symbol,
            snapshot_date=snapshot_date,
            window_days=window_days,
            report_count=len(reports),
            avg_target_price=avg_target,
            min_target_price=min(targets) if targets else None,
            max_target_price=max(targets) if targets else None,
            latest_published_at=latest_pub,
            **rating_counts,
        )
        snapshots_upserted += 1

    return JobResult(
        status=JOB_STATUS_SUCCESS,
        summary={
            "phase": "v0.4-B",
            "snapshot_date": snapshot_date.isoformat(),
            "window_days": window_days,
            "data_status": "SUCCESS",
            "active_reports": len(rows),
            "symbols_processed": len(by_symbol),
            "snapshots_upserted": snapshots_upserted,
        },
    )


# ---------- 19:00 collect_news (v0.5 Phase A PR2) ----------


def _resolve_news_provider(session: Session):
    """Return the injected ``news_provider`` if any, else ``None``.

    v0.5 Phase A 에서는 실 RSS / Naver 금융 / DART 등 외부 provider 구현체가
    아직 없다. 운영 환경에서는 ``session.info["news_provider"]`` 가 비어 있는
    상태이며, ``collect_news`` 잡은 enabled=true 라도 provider 부재 시 SKIPPED
    분기로 즉시 종료한다 (외부 호출 0건). 테스트는 FakeNewsProvider 를 동일
    경로로 주입한다.
    """
    return session.info.get("news_provider")


def collect_news(session: Session) -> JobResult:
    """Collect recent news metadata when ``news_collection_enabled`` is true.

    JobResult.status mapping:
      * NEWS_COLLECTION_ENABLED=false (default) → SUCCESS,
        data_status=SKIPPED, reason="news_collection_disabled". 외부 provider
        는 생성 / 호출되지 않는다.
      * NEWS_COLLECTION_ENABLED=true 이지만 ``session.info["news_provider"]``
        가 비어 있음 → SUCCESS, data_status=SKIPPED,
        reason="no_provider_configured". v0.5 Phase A 시점에는 실 provider
        구현체가 없으므로 운영 default 동작.
      * provider 가 주입되어 있음 → ``NewsCollector.collect_recent`` 실행
        후 SUCCESS + counters.

    KIS / Telegram / 외부 호출 0건. 실 provider 도입은 v0.5 Phase B+ 또는
    별도 cycle 의 RSS / DART 모듈 도입 후 자연스럽게 활성화된다.
    """
    from app.data.collectors import NewsCollector
    from app.data.repositories.news_items import NewsItemRepository

    settings = _resolve_settings(session)
    if not settings.news_collection_enabled:
        return JobResult(
            status=JOB_STATUS_SUCCESS,
            summary={
                "phase": "v0.5-A",
                "data_status": "SKIPPED",
                "reason": "news_collection_disabled",
                "fetched": 0,
                "inserted": 0,
                "skipped_duplicates": 0,
                "truncated_summaries": 0,
            },
        )

    provider = _resolve_news_provider(session)
    if provider is None:
        return JobResult(
            status=JOB_STATUS_SUCCESS,
            summary={
                "phase": "v0.5-A",
                "data_status": "SKIPPED",
                "reason": "no_provider_configured",
                "fetched": 0,
                "inserted": 0,
                "skipped_duplicates": 0,
                "truncated_summaries": 0,
            },
        )

    collector = NewsCollector(provider, NewsItemRepository(session))
    result = collector.collect_recent(limit=50)

    return JobResult(
        status=JOB_STATUS_SUCCESS,
        summary={
            "phase": "v0.5-A",
            "data_status": "SUCCESS",
            "fetched": result.fetched,
            "inserted": result.inserted,
            "skipped_duplicates": result.skipped_duplicates,
            "truncated_summaries": result.truncated_summaries,
        },
    )


# ---------- 20:00 collect_disclosures (v0.5 Phase B) ----------


def _resolve_disclosure_provider(session: Session):
    """Return the injected ``disclosure_provider`` if any, else ``None``.

    Same injection pattern as :func:`_resolve_news_provider`. v0.5 Phase B 시점
    에는 실 DART / KRX provider 구현체가 없으므로 운영 default 동작은
    ``enabled=true + provider 미주입 → SKIPPED``.
    """
    return session.info.get("disclosure_provider")


def collect_disclosures(session: Session) -> JobResult:
    """Collect recent disclosure metadata when ``disclosure_collection_enabled`` is true.

    JobResult.status mapping (mirrors :func:`collect_news`):
      * DISCLOSURE_COLLECTION_ENABLED=false (default) → SUCCESS,
        data_status=SKIPPED, reason="disclosure_collection_disabled".
      * enabled=true 이지만 provider 미주입 → SUCCESS, data_status=SKIPPED,
        reason="no_provider_configured".
      * enabled=true + provider 주입 → ``DisclosureCollector.collect_recent``
        실행 후 SUCCESS + counters + classified_counts.
    """
    from app.data.collectors import DisclosureCollector
    from app.data.repositories.news_items import NewsItemRepository

    settings = _resolve_settings(session)
    if not settings.disclosure_collection_enabled:
        return JobResult(
            status=JOB_STATUS_SUCCESS,
            summary={
                "phase": "v0.5-B",
                "data_status": "SKIPPED",
                "reason": "disclosure_collection_disabled",
                "fetched": 0,
                "inserted": 0,
                "skipped_duplicates": 0,
                "truncated_summaries": 0,
            },
        )

    provider = _resolve_disclosure_provider(session)
    if provider is None:
        return JobResult(
            status=JOB_STATUS_SUCCESS,
            summary={
                "phase": "v0.5-B",
                "data_status": "SKIPPED",
                "reason": "no_provider_configured",
                "fetched": 0,
                "inserted": 0,
                "skipped_duplicates": 0,
                "truncated_summaries": 0,
            },
        )

    collector = DisclosureCollector(provider, NewsItemRepository(session))
    result = collector.collect_recent(limit=50)

    return JobResult(
        status=JOB_STATUS_SUCCESS,
        summary={
            "phase": "v0.5-B",
            "data_status": "SUCCESS",
            "fetched": result.fetched,
            "inserted": result.inserted,
            "skipped_duplicates": result.skipped_duplicates,
            "truncated_summaries": result.truncated_summaries,
            "classified_counts": dict(result.classified_counts),
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
    JOB_NAME_UPDATE_REPORT_CONSENSUS: update_report_consensus_snapshots,
    JOB_NAME_COLLECT_NEWS: collect_news,
    JOB_NAME_COLLECT_DISCLOSURES: collect_disclosures,
}
