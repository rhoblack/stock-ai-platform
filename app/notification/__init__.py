"""Report and notification layer. This package must not change decisions."""

from app.notification.dispatchers import (
    HoldingCheckDispatchOutcome,
    HoldingCheckReportDispatcher,
    RecommendationDispatchOutcome,
    RecommendationReportDispatcher,
)
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
from app.notification.telegram_notifier import (
    NotificationResult,
    TelegramNotifier,
    mask_chat_id,
)

__all__ = [
    "HoldingCheckDispatchOutcome",
    "HoldingCheckReportDispatcher",
    "HoldingLine",
    "MESSAGE_TYPE_ALERT",
    "MESSAGE_TYPE_REPORT",
    "NotificationOutcome",
    "NotificationResult",
    "NotificationService",
    "RecommendationDispatchOutcome",
    "RecommendationLine",
    "RecommendationReportDispatcher",
    "ReportGenerator",
    "TelegramNotifier",
    "extract_risk_summary",
    "mask_chat_id",
]
