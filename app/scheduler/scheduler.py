"""APScheduler glue for the v0.1 daily job timeline.

Imports ``apscheduler`` only at module load — keep this file out of any code
path that runs in environments without the dependency. Tests should target
``app.scheduler.jobs`` (pure-Python job functions + the wrapper) and avoid
this module unless they explicitly need scheduling behavior.

Production startup (FastAPI lifespan in ``app.main``) calls ``build_scheduler``
when ``settings.scheduler_enabled`` is True and starts/stops it accordingly.
"""

from __future__ import annotations

from functools import partial

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from sqlalchemy.orm import Session, sessionmaker

from app.scheduler.jobs import (
    JOB_FUNCTIONS,
    JOB_NAME_CALCULATE_INDICATORS,
    JOB_NAME_COLLECT_DISCLOSURES,
    JOB_NAME_COLLECT_MARKET_CLOSE,
    JOB_NAME_COLLECT_NEWS,
    JOB_NAME_CREATE_PAPER_PNL_SNAPSHOT,
    JOB_NAME_EXECUTE_PAPER_ORDERS,
    JOB_NAME_EXPIRE_PENDING_APPROVALS,
    JOB_NAME_POST_MARKET_HOLDING_CHECK,
    JOB_NAME_PRE_MARKET_HOLDING_CHECK,
    JOB_NAME_SEND_RECOMMENDATION_REPORT,
    JOB_NAME_UPDATE_RECOMMENDATION_RESULTS,
    JOB_NAME_UPDATE_REPORT_CONSENSUS,
    JobOutcome,
    run_job,
)


# (hour, minute) per job — matches the v0.1 daily schedule in AGENTS.md.
# 06:30 KST consensus snapshot was added in v0.4 Phase B (after 06:00 telegram
# report and before 08:30 pre-market holding check) so the morning report can
# eventually consume yesterday's analyst-report consensus when v0.4 Phase C
# wires `report_score` into the recommendation engine.
# 19:00 KST collect_news (v0.5 Phase A PR2) and 20:00 KST collect_disclosures
# (v0.5 Phase B) — both default OFF via *_collection_enabled flags; SKIPPED
# by default to keep the daily timeline free of external calls until an
# operator opts in.
DEFAULT_SCHEDULE: dict[str, tuple[int, int]] = {
    JOB_NAME_COLLECT_MARKET_CLOSE: (18, 0),
    JOB_NAME_CALCULATE_INDICATORS: (18, 30),
    JOB_NAME_COLLECT_NEWS: (19, 0),
    JOB_NAME_COLLECT_DISCLOSURES: (20, 0),
    JOB_NAME_SEND_RECOMMENDATION_REPORT: (6, 0),
    JOB_NAME_UPDATE_REPORT_CONSENSUS: (6, 30),
    JOB_NAME_PRE_MARKET_HOLDING_CHECK: (8, 30),
    JOB_NAME_POST_MARKET_HOLDING_CHECK: (16, 30),
    JOB_NAME_UPDATE_RECOMMENDATION_RESULTS: (17, 0),
    # v0.14 Phase D — paper trading jobs.  Both default-OFF via
    # PAPER_TRADING_ENABLED; the job functions short-circuit to SKIPPED so
    # registering them here costs nothing in the disabled path.
    JOB_NAME_EXECUTE_PAPER_ORDERS: (16, 0),
    JOB_NAME_CREATE_PAPER_PNL_SNAPSHOT: (16, 30),
}


# v0.15 Phase D — interval-based jobs (every-N-minutes). Default-OFF via
# TRADING_SAFETY_ENABLED + KILL_SWITCH_ENABLED so this is harmless when
# the operator has not opted in.
DEFAULT_INTERVAL_SCHEDULE: dict[str, int] = {
    JOB_NAME_EXPIRE_PENDING_APPROVALS: 5,  # minutes
}


def _wrapped_runner(
    *,
    session_factory: sessionmaker[Session],
    job_name: str,
) -> JobOutcome:
    return run_job(
        session_factory=session_factory,
        job_name=job_name,
        fn=JOB_FUNCTIONS[job_name],
    )


def build_scheduler(
    *,
    session_factory: sessionmaker[Session],
    timezone: str = "Asia/Seoul",
    schedule: dict[str, tuple[int, int]] | None = None,
    interval_schedule: dict[str, int] | None = None,
) -> BackgroundScheduler:
    """Construct a configured BackgroundScheduler with the v0.1 jobs.

    The returned scheduler has NOT been started yet — callers (FastAPI lifespan
    or a CLI entry point) decide when to call ``.start()`` / ``.shutdown()``.

    Two trigger families:
      * ``schedule`` (cron, ``(hour, minute)``) — daily-cadence jobs.
      * ``interval_schedule`` (every-N-minutes) — Phase D's
        ``expire_pending_approvals`` (5-minute sweep).
    """
    # Use explicit None check so an explicit empty {} override actually means
    # "no jobs of this kind" -- distinguishes 'use defaults' from 'opt out'.
    effective_cron = (
        DEFAULT_SCHEDULE if schedule is None else schedule
    )
    effective_interval = (
        DEFAULT_INTERVAL_SCHEDULE
        if interval_schedule is None
        else interval_schedule
    )
    scheduler = BackgroundScheduler(timezone=timezone)

    for job_name in JOB_FUNCTIONS:
        if job_name in effective_cron:
            hour, minute = effective_cron[job_name]
            runner = partial(
                _wrapped_runner,
                session_factory=session_factory,
                job_name=job_name,
            )
            scheduler.add_job(
                runner,
                trigger=CronTrigger(hour=hour, minute=minute, timezone=timezone),
                id=job_name,
                name=job_name,
                replace_existing=True,
                misfire_grace_time=300,  # tolerate 5 min late firing
                coalesce=True,            # drop intermediate misfires
            )
        elif job_name in effective_interval:
            interval_minutes = effective_interval[job_name]
            runner = partial(
                _wrapped_runner,
                session_factory=session_factory,
                job_name=job_name,
            )
            scheduler.add_job(
                runner,
                trigger=IntervalTrigger(
                    minutes=interval_minutes, timezone=timezone
                ),
                id=job_name,
                name=job_name,
                replace_existing=True,
                misfire_grace_time=60,
                coalesce=True,
            )
    return scheduler
