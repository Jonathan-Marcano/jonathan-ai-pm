"""Provider-neutral messaging contracts and outbound confirmation policy (Phase 4, P4-01).

Messaging adapters follow the same safety discipline as Phase 2 providers, but Phase 4
deliberately has two directions. Inbound: provider messages become neutral, bounded capture
candidates for the existing inbox. Outbound: the workspace sends notices (briefs, reminders) only
after an explicit preview-and-confirm step; ``OutboundPolicy`` refuses any send whose token does
not match the preview digest of the message, so no notice ever leaves on its own.

There are no live network calls, OAuth flows, or credentials in this increment.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from hashlib import sha256
from typing import Protocol

from faroflow.integrations.contracts import (
    IntegrationCapabilities,
    IntegrationContractError,
)

MAX_MESSAGE_CHARS = 4000
MAX_MESSAGES_PER_LISTING = 200


def _required_identity(value: str, field_name: str) -> str:
    normalized = value.strip()
    if not normalized:
        raise IntegrationContractError(f"{field_name} cannot be empty")
    return normalized


def _as_utc(value: datetime, field_name: str) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise IntegrationContractError(f"{field_name} must include a timezone")
    return value.astimezone(UTC)


def _bounded_body(value: str) -> str:
    normalized = value.strip()
    if not normalized:
        raise IntegrationContractError("message body cannot be empty")
    if len(normalized) > MAX_MESSAGE_CHARS:
        raise IntegrationContractError(
            f"message body exceeds the {MAX_MESSAGE_CHARS} character limit"
        )
    return normalized


class OutboundConfirmationError(IntegrationContractError):
    pass


@dataclass(frozen=True, slots=True)
class ExternalInboundMessage:
    """One normalized message a user sent into the workspace via a provider."""

    source_system: str
    conversation_id: str
    external_id: str
    text: str
    received_at: datetime
    sender_display: str | None = None

    def __post_init__(self) -> None:
        source_system = _required_identity(self.source_system, "source_system").lower()
        conversation_id = _required_identity(self.conversation_id, "conversation_id")
        external_id = _required_identity(self.external_id, "external_id")
        text = _bounded_body(self.text)
        received_at = _as_utc(self.received_at, "received_at")
        object.__setattr__(self, "source_system", source_system)
        object.__setattr__(self, "conversation_id", conversation_id)
        object.__setattr__(self, "external_id", external_id)
        object.__setattr__(self, "text", text)
        object.__setattr__(self, "received_at", received_at)

    @property
    def source_key(self) -> tuple[str, str, str]:
        return self.source_system, self.conversation_id, self.external_id


@dataclass(frozen=True, slots=True)
class OutboundNotice:
    """A neutral, bounded message the workspace intends to send after confirmation."""

    source_system: str
    destination: str
    body: str
    reply_to_conversation_id: str | None = None

    def __post_init__(self) -> None:
        source_system = _required_identity(self.source_system, "source_system").lower()
        destination = _required_identity(self.destination, "destination")
        body = _bounded_body(self.body)
        reply_to_conversation_id = (
            _required_identity(self.reply_to_conversation_id, "reply_to_conversation_id")
            if self.reply_to_conversation_id
            else None
        )
        object.__setattr__(self, "source_system", source_system)
        object.__setattr__(self, "destination", destination)
        object.__setattr__(self, "body", body)
        object.__setattr__(self, "reply_to_conversation_id", reply_to_conversation_id)


@dataclass(frozen=True, slots=True)
class ExternalMessageReceipt:
    """Provider identity of an outbound message that was actually sent."""

    source_system: str
    external_id: str
    sent_at: datetime

    def __post_init__(self) -> None:
        source_system = _required_identity(self.source_system, "source_system").lower()
        external_id = _required_identity(self.external_id, "external_id")
        sent_at = _as_utc(self.sent_at, "sent_at")
        object.__setattr__(self, "source_system", source_system)
        object.__setattr__(self, "external_id", external_id)
        object.__setattr__(self, "sent_at", sent_at)

    @property
    def source_key(self) -> tuple[str, str]:
        return self.source_system, self.external_id


def outbound_preview_digest(notice: OutboundNotice) -> str:
    """Content-addressed digest of the exact message a user must confirm."""
    material = "\u001e".join(
        (
            notice.source_system,
            notice.destination,
            notice.body,
            notice.reply_to_conversation_id or "",
        )
    )
    return sha256(material.encode("utf-8")).hexdigest()


@dataclass(frozen=True, slots=True)
class OutboundPolicy:
    """Gate that refuses outbound sends without an explicit user confirmation."""

    max_message_chars: int = MAX_MESSAGE_CHARS
    require_confirmation: bool = True

    def __post_init__(self) -> None:
        if self.max_message_chars < 1:
            raise IntegrationContractError("max_message_chars must be positive")

    def assert_can_send(
        self,
        notice: OutboundNotice,
        *,
        confirmation: str | None,
    ) -> None:
        if len(notice.body) > self.max_message_chars:
            raise IntegrationContractError(
                f"message body exceeds the {self.max_message_chars} character limit"
            )
        if not self.require_confirmation:
            return
        if confirmation != outbound_preview_digest(notice):
            raise OutboundConfirmationError(
                "outbound send requires an explicit user confirmation that matches the preview"
            )


class MessagingAdapter(Protocol):
    """A provider-neutral messaging adapter with inbound and confirmed outbound channels."""

    source_system: str
    capabilities: IntegrationCapabilities

    def list_messages(
        self,
        conversation_ids: Sequence[str],
        since: datetime,
    ) -> list[ExternalInboundMessage]: ...

    def send(self, notice: OutboundNotice) -> ExternalMessageReceipt: ...