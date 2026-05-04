from datetime import datetime

import httpx
import pytest

from app.config.settings import Settings
from app.data.repositories import JobRunRepository, NotificationLogRepository
from app.db import Base
from app.db.models import JobRun
from app.db.session import create_db_engine, create_session_factory
from app.notification.notification_service import (
    MESSAGE_TYPE_ALERT,
    MESSAGE_TYPE_REPORT,
    NotificationOutcome,
    NotificationService,
)
from app.notification.telegram_notifier import TelegramNotifier


@pytest.fixture()
def session():
    engine = create_db_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    factory = create_session_factory(engine)
    db_session = factory()
    try:
        yield db_session
    finally:
        db_session.close()
        Base.metadata.drop_all(engine)


def _settings(**overrides) -> Settings:
    defaults = {
        "telegram_enabled": False,
        "telegram_bot_token": "fake_test_token",
        "telegram_chat_id": "1234567890",
        "telegram_api_base_url": "https://mock-telegram.local",
        "telegram_timeout_seconds": 5,
    }
    defaults.update(overrides)
    return Settings(**defaults)


def _notifier(settings: Settings, handler) -> TelegramNotifier:
    http = httpx.Client(
        transport=httpx.MockTransport(handler),
        base_url=settings.telegram_api_base_url,
    )
    return TelegramNotifier(settings=settings, http_client=http)


def _service(session, notifier) -> NotificationService:
    return NotificationService(
        notifier=notifier,
        log_repository=NotificationLogRepository(session),
    )


# ---------- dry-run path ----------

def test_dry_run_records_log_with_status_dry_run_and_no_sent_at(session):
    def handler(request: httpx.Request) -> httpx.Response:
        raise AssertionError("HTTP must not be called when telegram_enabled is False")

    settings = _settings(telegram_enabled=False)
    service = _service(session, _notifier(settings, handler))

    outcome = service.send_telegram(
        message="dry run test",
        message_type=MESSAGE_TYPE_REPORT,
    )
    session.commit()

    assert isinstance(outcome, NotificationOutcome)
    assert outcome.status == "DRY_RUN"
    assert outcome.sent is False
    assert outcome.target == "12****90"

    logs = NotificationLogRepository(session).list()
    assert len(logs) == 1
    log = logs[0]
    assert log.id == outcome.notification_log_id
    assert log.channel == "TELEGRAM"
    assert log.message_type == MESSAGE_TYPE_REPORT
    assert log.target == "12****90"
    assert log.sent_at is None
    assert log.status == "DRY_RUN"
    assert log.error_message is None
    assert log.related_job_id is None


# ---------- success path ----------

def test_success_records_log_with_sent_at_populated(session):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"ok": True, "result": {"message_id": 7}})

    settings = _settings(telegram_enabled=True)
    service = _service(session, _notifier(settings, handler))

    outcome = service.send_telegram(
        message="hello",
        message_type=MESSAGE_TYPE_REPORT,
    )
    session.commit()

    assert outcome.status == "SUCCESS"
    assert outcome.sent is True

    log = NotificationLogRepository(session).list()[0]
    assert log.status == "SUCCESS"
    assert log.sent_at is not None
    assert isinstance(log.sent_at, datetime)
    assert log.error_message is None


# ---------- failure path ----------

def test_failed_send_records_error_message(session):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"ok": False, "description": "chat not found"})

    settings = _settings(telegram_enabled=True)
    service = _service(session, _notifier(settings, handler))

    outcome = service.send_telegram(
        message="hello",
        message_type=MESSAGE_TYPE_ALERT,
    )
    session.commit()

    assert outcome.status == "FAILED"
    assert outcome.sent is False

    log = NotificationLogRepository(session).list()[0]
    assert log.status == "FAILED"
    assert log.sent_at is None
    assert log.message_type == MESSAGE_TYPE_ALERT
    assert "chat not found" in log.error_message


def test_disabled_when_credentials_missing(session):
    def handler(request: httpx.Request) -> httpx.Response:
        raise AssertionError("HTTP must not be called without credentials")

    settings = _settings(telegram_enabled=True, telegram_bot_token="")
    service = _service(session, _notifier(settings, handler))

    outcome = service.send_telegram(
        message="hello",
        message_type=MESSAGE_TYPE_REPORT,
    )
    session.commit()

    assert outcome.status == "DISABLED"
    log = NotificationLogRepository(session).list()[0]
    assert log.status == "DISABLED"
    assert log.error_message == "missing telegram credentials"


# ---------- related job linkage ----------

def test_notification_log_links_to_job_run(session):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"ok": True})

    job = JobRunRepository(session).add(
        JobRun(
            job_name="send_recommendation_report",
            started_at=datetime(2026, 5, 4, 6, 0),
            finished_at=datetime(2026, 5, 4, 6, 1),
            status="SUCCESS",
        ),
    )
    session.flush()

    settings = _settings(telegram_enabled=True)
    service = _service(session, _notifier(settings, handler))

    outcome = service.send_telegram(
        message="hello",
        message_type=MESSAGE_TYPE_REPORT,
        related_job_id=job.job_id,
    )
    session.commit()

    log = NotificationLogRepository(session).list()[0]
    assert outcome.status == "SUCCESS"
    assert log.related_job_id == job.job_id
    assert log.related_job is job


# ---------- multiple sends accumulate logs ----------

def test_multiple_sends_create_multiple_log_rows(session):
    responses = [
        httpx.Response(200, json={"ok": True}),
        httpx.Response(200, json={"ok": False, "description": "rate limit"}),
    ]

    def handler(request: httpx.Request) -> httpx.Response:
        return responses.pop(0)

    settings = _settings(telegram_enabled=True)
    service = _service(session, _notifier(settings, handler))

    service.send_telegram(message="ok", message_type=MESSAGE_TYPE_REPORT)
    service.send_telegram(message="bad", message_type=MESSAGE_TYPE_ALERT)
    session.commit()

    logs = NotificationLogRepository(session).list()
    assert len(logs) == 2
    statuses = {log.status for log in logs}
    assert statuses == {"SUCCESS", "FAILED"}
