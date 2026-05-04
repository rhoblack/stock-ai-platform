"""NotificationService v0.1 — Phase 6 send-and-log glue.

Wraps a ``TelegramNotifier`` so callers (schedulers, manual triggers) can send
a message and have the outcome persisted in ``notification_logs`` in one call.
This module does not format messages (see ``ReportGenerator``) and does not
own the HTTP client (see ``TelegramNotifier``).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from app.data.repositories.notification_logs import NotificationLogRepository
from app.db.models import NotificationLog
from app.notification.telegram_notifier import (
    NotificationResult,
    TelegramNotifier,
)


MESSAGE_TYPE_REPORT = "REPORT"
MESSAGE_TYPE_ALERT = "ALERT"


@dataclass(frozen=True)
class NotificationOutcome:
    notification_log_id: int
    channel: str
    status: str
    sent: bool
    target: str
    error_message: str | None


class NotificationService:
    def __init__(
        self,
        *,
        notifier: TelegramNotifier,
        log_repository: NotificationLogRepository,
    ) -> None:
        self._notifier = notifier
        self._log_repository = log_repository

    def send_telegram(
        self,
        *,
        message: str,
        message_type: str,
        related_job_id: int | None = None,
    ) -> NotificationOutcome:
        result = self._notifier.send(message)
        log = self._record_log(
            result=result,
            message_type=message_type,
            related_job_id=related_job_id,
        )
        return NotificationOutcome(
            notification_log_id=log.id,
            channel=result.channel,
            status=result.status,
            sent=result.sent,
            target=result.target,
            error_message=result.error_message,
        )

    def _record_log(
        self,
        *,
        result: NotificationResult,
        message_type: str,
        related_job_id: int | None,
    ) -> NotificationLog:
        sent_at = datetime.now(UTC) if result.sent else None
        return self._log_repository.add(
            NotificationLog(
                channel=result.channel,
                message_type=message_type,
                target=result.target,
                sent_at=sent_at,
                status=result.status,
                error_message=result.error_message,
                related_job_id=related_job_id,
            ),
        )
