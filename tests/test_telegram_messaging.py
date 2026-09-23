from datetime import UTC, datetime

import pytest

from faroflow.integrations import (
    READ_ONLY_CAPABILITIES,
    TelegramMessagingAdapter,
    TelegramMessagingConfig,
    TelegramMessagingError,
    TelegramMessagingNotConfigured,
    build_telegram_messaging_adapter,
)


class FakeResponse:
    def __init__(self, payload, status_code=200):
        self.payload = payload
        self.status_code = status_code

    def json(self):
        return self.payload


class FakeHttpClient:
    def __init__(self, *responses):
        self.responses = list(responses)
        self.calls = []

    def get(self, url, *, params, headers, timeout):
        self.calls.append({"url": url, "params": params, "headers": headers, "timeout": timeout})
        return self.responses.pop(0)


def text_update(update_id=1, message_id=10, chat_id=42, text="Buy milk", date=1760000000,
                first_name=None):
    payload = {
        "update_id": update_id,
        "message": {
            "message_id": message_id,
            "date": date,
            "text": text,
            "chat": {"id": chat_id, "type": "private"},
        },
    }
    if first_name:
        payload["message"]["from"] = {"id": chat_id, "first_name": first_name}
    return payload


def adapter(config=None, http_client=None):
    return TelegramMessagingAdapter(
        lambda: "test-token",
        config=config or TelegramMessagingConfig(required_chat_ids=("42",)),
        http_client=http_client or FakeHttpClient(),
    )


SINCE = datetime.fromtimestamp(1759900000, tz=UTC)


def test_adapter_scopes_conversations_and_parses_messages() -> None:
    client = FakeHttpClient(
        FakeResponse({"ok": True, "result": [
            text_update(update_id=5, message_id=50, chat_id=42, text="Pagar la luz",
                        first_name="Ana"),
            text_update(update_id=6, message_id=51, chat_id=99, text="Fuera de scope"),
        ]})
    )
    found = adapter(http_client=client).list_messages(["42"], SINCE)

    assert [m.external_id for m in found] == ["50"]
    assert found[0].source_key == ("telegram", "42", "50")
    assert found[0].text == "Pagar la luz"
    assert found[0].sender_display == "Ana"
    assert found[0].received_at == datetime(2025, 10, 9, 8, 53, 20, tzinfo=UTC)
    call = client.calls[0]
    assert call["url"] == "https://api.telegram.org/bottest-token/getUpdates"
    assert call["params"]["limit"] == 100


def test_adapter_filters_out_old_and_non_text_updates() -> None:
    client = FakeHttpClient(
        FakeResponse({"ok": True, "result": [
            text_update(update_id=1, message_id=10, chat_id=42, text="Reciente", date=1760000000),
            text_update(update_id=2, message_id=11, chat_id=42, text="Viejo", date=1750000000),
            {"update_id": 3, "channel_post": {"message_id": 12, "chat": {"id": 42}}},
            {"update_id": 4, "message": {"message_id": 13, "date": 1760000000,
                                          "chat": {"id": 42}}},
        ]})
    )

    found = adapter(http_client=client).list_messages(["42"], SINCE)

    assert [m.external_id for m in found] == ["10"]
    assert [m.text for m in found] == ["Reciente"]


def test_adapter_advances_offset_on_each_page() -> None:
    client = FakeHttpClient(
        FakeResponse({"ok": True, "result": [
            text_update(update_id=100, message_id=50, chat_id=42),
            text_update(update_id=101, message_id=51, chat_id=42),
        ]}),
        FakeResponse({"ok": True, "result": [
            text_update(update_id=102, message_id=52, chat_id=42),
        ]}),
    )

    found = adapter(
        config=TelegramMessagingConfig(required_chat_ids=("42",), max_updates=5, page_size=2),
        http_client=client,
    ).list_messages(["42"], SINCE)

    assert [m.external_id for m in found] == ["50", "51", "52"]
    assert client.calls[1]["params"]["offset"] == 102


def test_adapter_rejects_remote_errors() -> None:
    client = FakeHttpClient(FakeResponse({"ok": False}, status_code=500))
    with pytest.raises(TelegramMessagingError, match="HTTP 500"):
        adapter(http_client=client).list_messages(["42"], SINCE)


def test_adapter_rejects_missing_token() -> None:
    with pytest.raises(TelegramMessagingError, match="token"):
        TelegramMessagingAdapter(
            lambda: "",
            config=TelegramMessagingConfig(required_chat_ids=("42",)),
            http_client=FakeHttpClient(FakeResponse({"ok": True, "result": []})),
        ).list_messages(["42"], SINCE)


def test_adapter_refuses_unscoped_poll() -> None:
    unscoped = TelegramMessagingAdapter(
        lambda: "test-token",
        config=TelegramMessagingConfig(required_chat_ids=()),
        http_client=FakeHttpClient(),
    )
    with pytest.raises(TelegramMessagingError, match="No conversations"):
        unscoped.list_messages([], SINCE)


def test_adapter_send_is_not_authorized() -> None:
    with pytest.raises(TelegramMessagingError, match="not authorized"):
        adapter().send(object())


def test_adapter_is_read_only_and_compatible_with_inbound_contract() -> None:
    assert adapter().capabilities == READ_ONLY_CAPABILITIES
    assert adapter().source_system == "telegram"


def test_build_adapter_raises_not_configured() -> None:
    with pytest.raises(TelegramMessagingNotConfigured):
        build_telegram_messaging_adapter()


def test_config_validates_bounds() -> None:
    with pytest.raises(TelegramMessagingError, match="max_updates"):
        TelegramMessagingConfig(max_updates=0)
    with pytest.raises(TelegramMessagingError, match="max_pages"):
        TelegramMessagingConfig(max_pages=999)
    with pytest.raises(TelegramMessagingError, match="timeout"):
        TelegramMessagingConfig(timeout_seconds=-1)


def test_adapter_bounds_listing_at_max_updates() -> None:
    messages = [text_update(update_id=1000 + i, message_id=100 + i, chat_id=42) for i in range(5)]
    client = FakeHttpClient(FakeResponse({"ok": True, "result": messages}))

    found = adapter(
        config=TelegramMessagingConfig(required_chat_ids=("42",), max_updates=3),
        http_client=client,
    ).list_messages(["42"], SINCE)

    assert len(found) == 3