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
from sqlalchemy.orm import Session, sessionmaker

from app.scheduler.jobs import (
    JOB_FUNCTIONS,
    JOB_NAME_CALCULATE_INDICATORS,
    JOB_NAME_COLLECT_MARKET_CLOSE,
    JOB_NAME_POST_MARKET_HOLDING_CHECK,
    JOB_NAME_PRE_MARKET_HOLDING_CHECK,
    JOB_NAME_SEND_RECOMMENDATION_REPORT,
    JOB_NAME_UPDATE_RECOMMENDATION_RESULTS,
    JobOutcome,
    run_job,
)


# (hour, minute) per job — matches the v0.1 daily schedule in AGENTS.md.
DEFAULT_SCHEDULE: dict[str, tuple[int, int]] = {
    JOB_NAME_COLLECT_MARKET_CLOSE: (18, 0),
    JOB_NAME_CALCULATE_INDICATORS: (18, 30),
    JOB_NAME_SEND_RECOMMENDATION_REPORT: (6, 0),
    JOB_NAME_PRE_MARKET_HOLDING_CHECK: (8, 30),
    JOB_NAME_POST_MARKET_HOLDING_CHECK: (16, 30),
    JOB_NAME_UPDATE_RECOMMENDATION_RESULTS: (17, 0),
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
) -> BackgroundScheduler:
    """Construct a configured BackgroundScheduler with the v0.1 jobs.

    The returned scheduler has NOT been started yet — callers (FastAPI lifespan
    or a CLI entry point) decide when to call ``.start()`` / ``.shutdown()``.
    """
    effective_schedule = schedule or DEFAULT_SCHEDULE
    scheduler = BackgroundScheduler(timezone=timezone)
    for job_name in JOB_FUNCTIONS:
        if job_name not in effective_schedule:
            continue
        hour, minute = effective_schedule[job_name]
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
    return scheduler
