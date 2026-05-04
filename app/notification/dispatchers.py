"""Dispatcher glue between engine results and the Telegram notification path.

A dispatcher loads the relevant ORM rows (recommendations + snapshots, or
holding_checks + snapshots), feeds them through ``ReportGenerator``, and
posts the message text through a ``NotificationService``. When the
``NotificationService`` runs in DRY_RUN mode (``settings.telegram_enabled``
is False) nothing is actually sent, but a notification_logs row is still
written and dispatcher outcomes carry the resulting status.

Boundary rules (Phase 8 follow-up):
    * No engine logic here — dispatchers are read-only against the engines'
      output.
    * No score recomputation, no risk recomputation.
    * No KIS / external HTTP calls beyond the Telegram BOT API call inside
      ``TelegramNotifier`` (which itself respects ``telegram_enabled``).
    * No order placement.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from app.data.repositories.holding_checks import HoldingCheckRepository
from app.data.repositories.recommendations import (
    RecommendationRepository,
    RecommendationRunRepository,
)
from app.data.repositories.notification_logs import NotificationLogRepository
from app.data.repositories.snapshots import DataSnapshotRepository
from app.notification.notification_service import (
    MESSAGE_TYPE_ALERT,
    MESSAGE_TYPE_REPORT,
    NotificationOutcome,
    NotificationService,
)
from app.notification.report_generator import (
    HoldingLine,
    RecommendationLine,
    ReportGenerator,
    extract_risk_summary,
)


_VALID_HOLDING_CHECK_TYPES = {"PRE_MARKET", "POST_MARKET"}
_ALERT_TYPE_HIGH_RISK = "HIGH_RISK"
_ALERT_TYPE_CHECK_ALERT = "CHECK_ALERT"


@dataclass(frozen=True)
class RecommendationDispatchOutcome:
    run_id: int
    recommendation_count: int
    notification: NotificationOutcome
    message_text: str
    telegram_sent_flag_updated: bool


@dataclass(frozen=True)
class HoldingCheckDispatchOutcome:
    check_date: date
    check_type: str
    holding_check_count: int
    notification: NotificationOutcome
    message_text: str


class RecommendationReportDispatcher:
    def __init__(
        self,
        *,
        report_generator: ReportGenerator,
        notification_service: NotificationService,
        run_repository: RecommendationRunRepository,
        recommendation_repository: RecommendationRepository,
        snapshot_repository: DataSnapshotRepository,
    ) -> None:
        self._report_generator = report_generator
        self._notification_service = notification_service
        self._run_repository = run_repository
        self._recommendation_repository = recommendation_repository
        self._snapshot_repository = snapshot_repository

    def dispatch(
        self,
        *,
        run_id: int,
        related_job_id: int | None = None,
    ) -> RecommendationDispatchOutcome:
        run = self._run_repository.get(run_id)
        if run is None:
            raise ValueError(f"recommendation run {run_id} not found")

        recommendations = self._recommendation_repository.list_by_run_id(run_id)
        lines: list[RecommendationLine] = []
        for rec in recommendations:
            snapshot = (
                self._snapshot_repository.get(rec.snapshot_id)
                if rec.snapshot_id is not None
                else None
            )
            level, flags = extract_risk_summary(snapshot)
            lines.append(
                RecommendationLine(
                    recommendation=rec,
                    risk_level=level,
                    risk_flags=flags,
                ),
            )

        message = self._report_generator.recommendation_report(
            run=run,
            lines=lines,
        )
        notification = self._notification_service.send_telegram(
            message=message,
            message_type=MESSAGE_TYPE_REPORT,
            related_job_id=related_job_id,
        )

        flag_updated = False
        # ``telegram_sent`` reflects an actual delivery (DRY_RUN/DISABLED/FAILED
        # do NOT mark the run as sent). The notification_logs row preserves the
        # full status independently.
        if notification.sent:
            run.telegram_sent = True
            self._run_repository.session.flush()
            flag_updated = True

        return RecommendationDispatchOutcome(
            run_id=run_id,
            recommendation_count=len(recommendations),
            notification=notification,
            message_text=message,
            telegram_sent_flag_updated=flag_updated,
        )


class HoldingCheckReportDispatcher:
    def __init__(
        self,
        *,
        report_generator: ReportGenerator,
        notification_service: NotificationService,
        holding_check_repository: HoldingCheckRepository,
        snapshot_repository: DataSnapshotRepository,
    ) -> None:
        self._report_generator = report_generator
        self._notification_service = notification_service
        self._holding_check_repository = holding_check_repository
        self._snapshot_repository = snapshot_repository

    def dispatch(
        self,
        *,
        check_date: date,
        check_type: str,
        related_job_id: int | None = None,
    ) -> HoldingCheckDispatchOutcome:
        if check_type not in _VALID_HOLDING_CHECK_TYPES:
            raise ValueError(
                f"check_type must be one of {sorted(_VALID_HOLDING_CHECK_TYPES)}, "
                f"got {check_type!r}",
            )

        checks = self._holding_check_repository.list_by_date_type(
            check_date=check_date,
            check_type=check_type,
        )
        lines: list[HoldingLine] = []
        for check in checks:
            snapshot = (
                self._snapshot_repository.get(check.snapshot_id)
                if check.snapshot_id is not None
                else None
            )
            level, flags = extract_risk_summary(snapshot)
            lines.append(
                HoldingLine(
                    check=check,
                    risk_level=level,
                    risk_flags=flags,
                ),
            )

        if check_type == "PRE_MARKET":
            message = self._report_generator.pre_market_holding_report(
                check_date=check_date,
                lines=lines,
            )
        else:
            message = self._report_generator.post_market_holding_report(
                check_date=check_date,
                lines=lines,
            )

        notification = self._notification_service.send_telegram(
            message=message,
            message_type=MESSAGE_TYPE_REPORT,
            related_job_id=related_job_id,
        )

        return HoldingCheckDispatchOutcome(
            check_date=check_date,
            check_type=check_type,
            holding_check_count=len(checks),
            notification=notification,
            message_text=message,
        )


class HoldingRiskAlertDispatcher:
    def __init__(
        self,
        *,
        report_generator: ReportGenerator,
        notification_service: NotificationService,
        holding_check_repository: HoldingCheckRepository,
        snapshot_repository: DataSnapshotRepository,
        log_repository: NotificationLogRepository,
    ) -> None:
        self._report_generator = report_generator
        self._notification_service = notification_service
        self._holding_check_repository = holding_check_repository
        self._snapshot_repository = snapshot_repository
        self._log_repository = log_repository

    def dispatch(
        self,
        *,
        check_date: date,
        check_type: str,
        related_job_id: int | None = None,
    ) -> int:
        if check_type not in _VALID_HOLDING_CHECK_TYPES:
            raise ValueError(f"invalid check_type: {check_type}")

        checks = self._holding_check_repository.list_by_date_type(
            check_date=check_date,
            check_type=check_type,
        )

        sent_targets = {
            log.target
            for log in self._log_repository.list()
            if log.message_type == MESSAGE_TYPE_ALERT
        }
        dispatched_count = 0

        for check in checks:
            snapshot = (
                self._snapshot_repository.get(check.snapshot_id)
                if check.snapshot_id
                else None
            )
            level, flags = extract_risk_summary(snapshot)
            alert_type = self._resolve_alert_type(alert=check.alert, risk_level=level)

            if alert_type is None:
                continue

            dedup_target = _holding_alert_target(
                symbol=check.symbol,
                check_date=check_date,
                check_type=check_type,
                alert_type=alert_type,
            )
            if dedup_target in sent_targets:
                continue

            line = HoldingLine(check=check, risk_level=level, risk_flags=flags)
            message = self._report_generator.risk_alert(line=line)

            self._notification_service.send_telegram(
                message=message,
                message_type=MESSAGE_TYPE_ALERT,
                target=dedup_target,
                related_job_id=related_job_id,
            )
            dispatched_count += 1
            sent_targets.add(dedup_target)

        return dispatched_count

    @staticmethod
    def _resolve_alert_type(*, alert: bool, risk_level: str) -> str | None:
        if risk_level == "HIGH":
            return _ALERT_TYPE_HIGH_RISK
        if alert:
            return _ALERT_TYPE_CHECK_ALERT
        return None


def _holding_alert_target(
    *,
    symbol: str,
    check_date: date,
    check_type: str,
    alert_type: str,
) -> str:
    return (
        "ALERT_HOLDING:"
        f"{symbol}:{check_date.isoformat()}:{check_type}:{alert_type}"
    )
