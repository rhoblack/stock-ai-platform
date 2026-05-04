"""TelegramNotifier v0.1 — Phase 6 Telegram BOT API client.

Sends a single text message via ``POST /bot<TOKEN>/sendMessage``. When
``settings.telegram_enabled`` is False the notifier returns a ``DRY_RUN``
result without making any HTTP call (the default for v0.1 + tests). When
credentials are missing it returns a ``DISABLED`` result.

Tests must inject an ``httpx.Client`` (e.g. ``httpx.MockTransport``) and
must NEVER reach the real Telegram service. The bot token never appears in
``NotificationResult.target`` or in error messages — only the chat_id is
masked and surfaced.
"""

from __future__ import annotations

from dataclasses import dataclass

import httpx

from app.config.settings import Settings


_NOTIFICATION_CHANNEL = "TELEGRAM"
_STATUS_SUCCESS = "SUCCESS"
_STATUS_DRY_RUN = "DRY_RUN"
_STATUS_DISABLED = "DISABLED"
_STATUS_FAILED = "FAILED"


@dataclass(frozen=True)
class NotificationResult:
    channel: str
    sent: bool
    target: str
    status: str
    error_message: str | None


def mask_chat_id(chat_id: str | None) -> str:
    if not chat_id:
        return ""
    if len(chat_id) <= 4:
        return "****"
    return f"{chat_id[:2]}****{chat_id[-2:]}"


class TelegramNotifier:
    SEND_PATH_TEMPLATE = "/bot{token}/sendMessage"

    def __init__(
        self,
        *,
        settings: Settings,
        http_client: httpx.Client | None = None,
    ) -> None:
        self._settings = settings
        self._owns_http_client = http_client is None
        self._http = http_client or httpx.Client(
            base_url=settings.telegram_api_base_url,
            timeout=settings.telegram_timeout_seconds,
        )

    def close(self) -> None:
        if self._owns_http_client:
            self._http.close()

    def __enter__(self) -> "TelegramNotifier":
        return self

    def __exit__(self, *_exc_info: object) -> None:
        self.close()

    def send(self, message: str) -> NotificationResult:
        masked_target = mask_chat_id(self._settings.telegram_chat_id)

        if not self._settings.telegram_enabled:
            return NotificationResult(
                channel=_NOTIFICATION_CHANNEL,
                sent=False,
                target=masked_target,
                status=_STATUS_DRY_RUN,
                error_message=None,
            )

        if (
            not self._settings.telegram_bot_token
            or not self._settings.telegram_chat_id
        ):
            return NotificationResult(
                channel=_NOTIFICATION_CHANNEL,
                sent=False,
                target=masked_target,
                status=_STATUS_DISABLED,
                error_message="missing telegram credentials",
            )

        path = self.SEND_PATH_TEMPLATE.format(
            token=self._settings.telegram_bot_token,
        )
        payload = {
            "chat_id": self._settings.telegram_chat_id,
            "text": message,
        }

        try:
            response = self._http.post(path, json=payload)
        except httpx.TimeoutException:
            return NotificationResult(
                channel=_NOTIFICATION_CHANNEL,
                sent=False,
                target=masked_target,
                status=_STATUS_FAILED,
                error_message="timeout",
            )
        except httpx.HTTPError as exc:
            return NotificationResult(
                channel=_NOTIFICATION_CHANNEL,
                sent=False,
                target=masked_target,
                status=_STATUS_FAILED,
                error_message=f"http error: {type(exc).__name__}",
            )

        if response.status_code >= 400:
            return NotificationResult(
                channel=_NOTIFICATION_CHANNEL,
                sent=False,
                target=masked_target,
                status=_STATUS_FAILED,
                error_message=f"HTTP {response.status_code}",
            )

        try:
            data = response.json()
        except ValueError:
            return NotificationResult(
                channel=_NOTIFICATION_CHANNEL,
                sent=False,
                target=masked_target,
                status=_STATUS_FAILED,
                error_message="invalid telegram response (not JSON)",
            )

        if not isinstance(data, dict) or not data.get("ok", False):
            description = (
                data.get("description")
                if isinstance(data, dict)
                else None
            )
            return NotificationResult(
                channel=_NOTIFICATION_CHANNEL,
                sent=False,
                target=masked_target,
                status=_STATUS_FAILED,
                error_message=str(description or "telegram api error"),
            )

        return NotificationResult(
            channel=_NOTIFICATION_CHANNEL,
            sent=True,
            target=masked_target,
            status=_STATUS_SUCCESS,
            error_message=None,
        )
