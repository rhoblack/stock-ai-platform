from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from app.db.session import create_session_factory


pytest.importorskip("apscheduler")


def _dummy_session_factory():
    # The scheduler module never opens sessions during build_scheduler; we just
    # need a callable that satisfies the type hint.
    return create_session_factory()


def test_build_scheduler_registers_six_jobs():
    from app.scheduler.scheduler import DEFAULT_SCHEDULE, build_scheduler

    scheduler = build_scheduler(
        session_factory=_dummy_session_factory(),
        timezone="Asia/Seoul",
    )
    try:
        job_ids = {job.id for job in scheduler.get_jobs()}
    finally:
        # Build_scheduler does not start; nothing to shut down. A no-op for safety.
        if scheduler.running:
            scheduler.shutdown(wait=False)

    assert job_ids == set(DEFAULT_SCHEDULE.keys())


def test_build_scheduler_cron_triggers_match_default_schedule():
    from app.scheduler.scheduler import DEFAULT_SCHEDULE, build_scheduler

    scheduler = build_scheduler(
        session_factory=_dummy_session_factory(),
        timezone="Asia/Seoul",
    )
    try:
        for job in scheduler.get_jobs():
            expected_hour, expected_minute = DEFAULT_SCHEDULE[job.id]
            trigger = job.trigger
            # APScheduler CronTrigger fields are accessible via .fields
            field_by_name = {f.name: f for f in trigger.fields}
            assert str(field_by_name["hour"]) == str(expected_hour)
            assert str(field_by_name["minute"]) == str(expected_minute)
    finally:
        if scheduler.running:
            scheduler.shutdown(wait=False)


def test_build_scheduler_does_not_start_automatically():
    from app.scheduler.scheduler import build_scheduler

    scheduler = build_scheduler(session_factory=_dummy_session_factory())
    try:
        assert scheduler.running is False
    finally:
        if scheduler.running:
            scheduler.shutdown(wait=False)


def test_build_scheduler_accepts_custom_schedule_overrides():
    from app.scheduler.jobs import JOB_NAME_COLLECT_MARKET_CLOSE
    from app.scheduler.scheduler import build_scheduler

    scheduler = build_scheduler(
        session_factory=_dummy_session_factory(),
        schedule={JOB_NAME_COLLECT_MARKET_CLOSE: (3, 15)},
    )
    try:
        jobs = list(scheduler.get_jobs())
        assert len(jobs) == 1
        job = jobs[0]
        assert job.id == JOB_NAME_COLLECT_MARKET_CLOSE
        field_by_name = {f.name: f for f in job.trigger.fields}
        assert str(field_by_name["hour"]) == "3"
        assert str(field_by_name["minute"]) == "15"
    finally:
        if scheduler.running:
            scheduler.shutdown(wait=False)


def test_scheduler_job_runner_uses_session_factory_when_invoked(monkeypatch):
    """Smoke test: invoking a registered job runs the wrapper, not the trigger."""
    from app.scheduler import jobs as jobs_module
    from app.scheduler.scheduler import build_scheduler

    captured = {}

    def fake_run_job(*, session_factory, job_name, fn):
        captured["job_name"] = job_name
        captured["fn"] = fn
        captured["session_factory"] = session_factory
        return jobs_module.JobOutcome(
            job_run_id=99,
            job_name=job_name,
            status=jobs_module.JOB_STATUS_SUCCESS,
            started_at=datetime.now(ZoneInfo("UTC")),
            finished_at=datetime.now(ZoneInfo("UTC")),
            result_summary={"phase": "test"},
            error_message=None,
        )

    import app.scheduler.scheduler as scheduler_module

    monkeypatch.setattr(scheduler_module, "run_job", fake_run_job)

    factory = _dummy_session_factory()
    scheduler = build_scheduler(session_factory=factory)
    try:
        job = scheduler.get_job(jobs_module.JOB_NAME_PRE_MARKET_HOLDING_CHECK)
        result = job.func()
        assert captured["job_name"] == jobs_module.JOB_NAME_PRE_MARKET_HOLDING_CHECK
        assert captured["session_factory"] is factory
        assert result.status == jobs_module.JOB_STATUS_SUCCESS
    finally:
        if scheduler.running:
            scheduler.shutdown(wait=False)
