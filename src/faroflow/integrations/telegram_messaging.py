"""Telegram Bot API messaging adapter (Phase 4, P4-02).

The adapter only reads the conversations the workspace explicitly scopes
(``required_chat_ids``) and returns bounded ``ExternalInboundMessage`` values from the
Bot API ``getUpdates`` endpoint. Outbound sending is deliberately not authorized yet
(P4-03): ``send`` raises until the preview-and-confirm path is implemented, so no notice
can ever leave on its own.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Protocol

import httpx

from faroflow.integrations.contracts import (
    READ_ONLY_CAPABILITIES,
    IntegrationCapabilities,
)
from faroflow.integrations.messaging import (
    MAX_MESSAGE_CHARS,
    MAX_MESSAGES_PER_LISTING,
    ExternalInboundMessage,
)

TELEGRAM_BOT_API_URL = "https://api.telegram.org"
TELEGRAM_GET_UPDATES_OFFSET = "getUpdates"
TELEGRAM_READ_SCOPE = "bots:read_updates"


class TelegramMessagingError(RuntimeError):
    pass


class TelegramMessagingNotConfigured(TelegramMessagingError):
    pass


class TelegramResponse(Protocol):
    status_code: int

    def json(self) -> Any: ...


class TelegramHttpClient(Protocol):
    def get(
        self,
        url: str,
        *,
        params: Mapping[str, str | int],
        headers: Mapping[str, str],
        timeout: float,
    ) -> TelegramResponse: ...


@dataclass(frozen=True, slots=True)
class TelegramMessagingConfig:
    """Bounded reading configuration for the Telegram Bot adapter."""

    required_chat_ids: tuple[str, ...] = ()
    max_updates: int = MAX_MESSAGES_PER_LISTING
    page_size: int = 100
    max_pages: int = 5
    timeout_seconds: float = 15.0

    def __post_init__(self) -> None:
        required_chat_ids = tuple(str(value).strip() for value in self.required_chat_ids)
        for chat_id in required_chat_ids:
            if not chat_id:
                raise TelegramMessagingError("required_chat_ids cannot contain empty ids")
        if isinstance(self.max_updates, bool) or not 1 <= self.max_updates <= 200:
            raise TelegramMessagingError("max_updates must be between 1 and 200")
        if isinstance(self.page_size, bool) or not 1 <= self.page_size <= 100:
            raise TelegramMessagingError("page_size must be between 1 and 100")
        if isinstance(self.max_pages, bool) or not 1 <= self.max_pages <= 50:
            raise TelegramMessagingError("max_pages must be between 1 and 50")
        if isinstance(self.timeout_seconds, bool) or self.timeout_seconds <= 0:
            raise TelegramMessagingError("timeout_seconds must be positive")
        object.__setattr__(self, "required_chat_ids", required_chat_ids)


class TelegramMessagingAdapter:
    """Read-only Telegram Bot adapter that converts bounded updates into inbound messages.

    The bot token is supplied by a callable at call time (never stored), updates are fetched
    through short polling bounded by ``max_updates * max_pages``, and only text messages within
    the scoped conversations are returned.
    """

    source_system = "telegram"
    capabilities: IntegrationCapabilities = READ_ONLY_CAPABILITIES
    delegated_scope = TELEGRAM_READ_SCOPE

    def __init__(
        self,
        token_provider: Callable[[], str],
        *,
        config: TelegramMessagingConfig | None = None,
        http_client: TelegramHttpClient | None = None,
    ) -> None:
        self.token_provider = token_provider
        self.config = config or TelegramMessagingConfig()
        self.http_client = http_client or httpx

    def list_messages(
        self,
        conversation_ids: Sequence[str],
        since: datetime,
    ) -> list[ExternalInboundMessage]:
        allowed = self._allowed_conversations(conversation_ids)
        if not allowed:
            raise TelegramMessagingError(
                "No conversations are scoped for this adapter; refuse to scan strangers' chats"
            )
        try:
            supplied_token = self.token_provider()
        except Exception:
            raise TelegramMessagingError("Telegram bot token is unavailable") from None
        if not isinstance(supplied_token, str) or not supplied_token.strip():
            raise TelegramMessagingError("Telegram bot token is unavailable")
        token = supplied_token.strip()

        url = f"{TELEGRAM_BOT_API_URL}/bot{token}/{TELEGRAM_GET_UPDATES_OFFSET}"
        headers = {"Accept": "application/json"}
        messages: list[ExternalInboundMessage] = []
        offset: int = 0
        for _page in range(1, self.config.max_pages + 1):
            params = {
                "timeout": 0,
                "limit": self.config.page_size,
            }
            if offset:
                params["offset"] = offset + 1
            try:
                response = self.http_client.get(
                    url,
                    params=params,
                    headers=headers,
                    timeout=self.config.timeout_seconds,
                )
            except httpx.HTTPError:
                raise TelegramMessagingError("Telegram request failed") from None
            if not 200 <= response.status_code < 300:
                raise TelegramMessagingError(
                    f"Telegram request failed with HTTP {response.status_code}"
                )
            try:
                payload = response.json()
            except (TypeError, ValueError):
                raise TelegramMessagingError("Telegram returned an invalid payload") from None
            if not isinstance(payload, dict) or payload.get("ok") is not True:
                raise TelegramMessagingError("Telegram rejected the updates request")
            updates = payload.get("result")
            if not isinstance(updates, list):
                raise TelegramMessagingError("Telegram returned an invalid updates listing")

            page_batch = [
                parsed
                for raw in updates
                if (parsed := self._parse_update(raw, since, allowed)) is not None
            ]
            messages.extend(page_batch)

            if not updates:
                break
            last_update_id = updates[-1].get("update_id") if isinstance(updates[-1], dict) else None
            if not isinstance(last_update_id, int):
                raise TelegramMessagingError("Telegram returned an invalid update id")
            offset = last_update_id
            if len(updates) < self.config.page_size:
                break
            if len(messages) >= self.config.max_updates:
                break

        return messages[:min(self.config.max_updates, MAX_MESSAGES_PER_LISTING)]

    def _allowed_conversations(self, requested: Sequence[str]) -> frozenset[str]:
        scoped = frozenset(self.config.required_chat_ids)
        requested_set = frozenset(str(value).strip() for value in requested if str(value).strip())
        if not scoped:
            return requested_set
        if not requested_set:
            return scoped
        return scoped & requested_set

    def _parse_update(
        self,
        raw: Any,
        since: datetime,
        allowed: frozenset[str],
    ) -> ExternalInboundMessage | None:
        if not isinstance(raw, dict):
            raise TelegramMessagingError("Telegram returned an invalid update")
        message = raw.get("message")
        if not isinstance(message, dict):
            return None
        text = message.get("text")
        if not isinstance(text, str) or not text.strip():
            return None
        chat = message.get("chat")
        if not isinstance(chat, dict):
            return None
        chat_id = chat.get("id")
        if isinstance(chat_id, bool):
            chat_id = None
        if chat_id is None:
            return None
        conversation_id = str(chat_id)
        if conversation_id not in allowed:
            return None
        external_id = message.get("message_id")
        if isinstance(external_id, bool) or not isinstance(external_id, int):
            return None
        raw_date = message.get("date")
        if isinstance(raw_date, bool) or not isinstance(raw_date, int):
            return None
        received_at = datetime.fromtimestamp(raw_date, tz=UTC)
        if received_at < since:
            return None
        sender = message.get("from")
        sender_display = None
        if isinstance(sender, dict):
            first_name = sender.get("first_name")
            if isinstance(first_name, str) and first_name.strip():
                sender_display = first_name.strip()
        return ExternalInboundMessage(
            source_system=self.source_system,
            conversation_id=conversation_id,
            external_id=str(external_id),
            text=text[:MAX_MESSAGE_CHARS],
            received_at=received_at,
            sender_display=sender_display,
        )

    def send(self, notice: object) -> object:
        raise TelegramMessagingError(
            "Outbound send is not authorized yet (P4-03 preview-and-confirm path pending)"
        )


def build_telegram_messaging_adapter() -> TelegramMessagingAdapter:
    """Build the runtime adapter once tenant authorization is supplied.

    Tenant authorization is not configured yet, so this helper intentionally raises
    ``TelegramMessagingNotConfigured``. The endpoint exposes that state as HTTP 503.
    """
    raise TelegramMessagingNotConfigured("Telegram messaging integration is not configured")