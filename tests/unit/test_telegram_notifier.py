import httpx

from app.config.settings import Settings
from app.notification.telegram_notifier import (
    TelegramNotifier,
    mask_chat_id,
)


def _settings(
    *,
    enabled: bool = True,
    bot_token: str = "fake_test_token",
    chat_id: str = "1234567890",
) -> Settings:
    return Settings(
        telegram_enabled=enabled,
        telegram_bot_token=bot_token,
        telegram_chat_id=chat_id,
        telegram_api_base_url="https://mock-telegram.local",
        telegram_timeout_seconds=5,
    )


def _notifier(settings: Settings, handler) -> TelegramNotifier:
    http = httpx.Client(
        transport=httpx.MockTransport(handler),
        base_url=settings.telegram_api_base_url,
    )
    return TelegramNotifier(settings=settings, http_client=http)


# ---------- masking ----------

def test_mask_chat_id_short_string():
    assert mask_chat_id("1234") == "****"


def test_mask_chat_id_long_string():
    assert mask_chat_id("1234567890") == "12****90"


def test_mask_chat_id_empty():
    assert mask_chat_id("") == ""
    assert mask_chat_id(None) == ""


# ---------- dry-run / disabled ----------

def test_dry_run_when_telegram_disabled_skips_http_call():
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json={"ok": True})

    notifier = _notifier(_settings(enabled=False), handler)
    result = notifier.send("hello")

    assert result.status == "DRY_RUN"
    assert result.sent is False
    assert result.error_message is None
    assert result.target == "12****90"
    assert seen == []


def test_disabled_when_token_missing_even_if_enabled():
    def handler(request: httpx.Request) -> httpx.Response:
        raise AssertionError("HTTP must not be called when credentials are missing")

    notifier = _notifier(_settings(enabled=True, bot_token=""), handler)
    result = notifier.send("hello")
    assert result.status == "DISABLED"
    assert result.sent is False
    assert "missing" in result.error_message.lower()


def test_disabled_when_chat_id_missing_even_if_enabled():
    def handler(request: httpx.Request) -> httpx.Response:
        raise AssertionError("HTTP must not be called when credentials are missing")

    notifier = _notifier(_settings(enabled=True, chat_id=""), handler)
    result = notifier.send("hello")
    assert result.status == "DISABLED"
    assert result.target == ""


# ---------- success ----------

def test_send_success_returns_status_success():
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["path"] = request.url.path
        captured["body"] = request.content.decode()
        return httpx.Response(200, json={"ok": True, "result": {"message_id": 42}})

    notifier = _notifier(_settings(), handler)
    result = notifier.send("hello world")

    assert result.status == "SUCCESS"
    assert result.sent is True
    assert result.error_message is None
    assert result.target == "12****90"
    assert captured["path"] == "/botfake_test_token/sendMessage"
    assert "hello world" in captured["body"]
    assert "1234567890" in captured["body"]


def test_send_uses_correct_chat_id_in_body():
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["body"] = request.content.decode()
        return httpx.Response(200, json={"ok": True})

    notifier = _notifier(_settings(chat_id="987654321"), handler)
    notifier.send("hi")
    assert "987654321" in captured["body"]


# ---------- failure paths ----------

def test_http_400_returns_failed():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"ok": False, "description": "Unauthorized"})

    notifier = _notifier(_settings(), handler)
    result = notifier.send("hello")
    assert result.status == "FAILED"
    assert result.sent is False
    assert "401" in result.error_message


def test_telegram_api_ok_false_returns_failed():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"ok": False, "description": "Bad Request"})

    notifier = _notifier(_settings(), handler)
    result = notifier.send("hello")
    assert result.status == "FAILED"
    assert "Bad Request" in result.error_message


def test_invalid_json_response_returns_failed():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text="not json")

    notifier = _notifier(_settings(), handler)
    result = notifier.send("hello")
    assert result.status == "FAILED"
    assert "JSON" in result.error_message


def test_timeout_returns_failed():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.TimeoutException("simulated timeout", request=request)

    notifier = _notifier(_settings(), handler)
    result = notifier.send("hello")
    assert result.status == "FAILED"
    assert result.error_message == "timeout"


def test_http_error_returns_failed():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.RequestError("simulated network error", request=request)

    notifier = _notifier(_settings(), handler)
    result = notifier.send("hello")
    assert result.status == "FAILED"
    assert "RequestError" in result.error_message


def test_token_does_not_appear_in_error_message():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"ok": False, "description": "Unauthorized"})

    notifier = _notifier(
        _settings(bot_token="super_secret_real_token_123"), handler,
    )
    result = notifier.send("hello")
    assert "super_secret_real_token_123" not in (result.error_message or "")
    assert "super_secret_real_token_123" not in result.target
