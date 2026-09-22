from datetime import UTC, datetime, timedelta, timezone

import pytest

from faroflow.integrations import (
    MAX_MESSAGE_CHARS,
    ExternalInboundMessage,
    ExternalMessageReceipt,
    IntegrationContractError,
    OutboundConfirmationError,
    OutboundNotice,
    OutboundPolicy,
    outbound_preview_digest,
)


def message(**overrides):
    base = {
        "source_system": "WhatsApp",
        "conversation_id": "chat-123",
        "external_id": "msg-a1",
        "text": "Buy the demo projector for tomorrow",
        "received_at": datetime(2026, 9, 16, 9, 0, tzinfo=UTC),
    }
    base.update(overrides)
    return ExternalInboundMessage(**base)


def test_inbound_message_identity_does_not_depend_on_content() -> None:
    original = message()
    duplicated = message(external_id="msg-a1")

    assert original.source_key == ("whatsapp", "chat-123", "msg-a1")
    assert duplicated.source_key == original.source_key


def test_inbound_message_normalizes_timezone_and_source() -> None:
    offset = timezone(-timedelta(hours=3))
    incoming = message(received_at=datetime(2026, 9, 16, 6, 0, tzinfo=offset))

    assert incoming.source_key[0] == "whatsapp"
    assert incoming.received_at.tzinfo is UTC
    assert incoming.received_at == datetime(2026, 9, 16, 9, 0, tzinfo=UTC)


def test_inbound_message_rejects_missing_identity_or_naive_time() -> None:
    with pytest.raises(IntegrationContractError, match="conversation_id"):
        message(conversation_id="   ")
    with pytest.raises(IntegrationContractError, match="external_id"):
        message(external_id="")
    with pytest.raises(IntegrationContractError, match="timezone"):
        message(received_at=datetime(2026, 9, 16, 9, 0))


def test_inbound_message_requires_non_empty_bounded_text() -> None:
    with pytest.raises(IntegrationContractError, match="empty"):
        message(text="   ")
    with pytest.raises(IntegrationContractError, match="character limit"):
        message(text="x" * (MAX_MESSAGE_CHARS + 1))


def test_outbound_notice_is_bounded_and_normalized() -> None:
    notice = OutboundNotice(
        source_system="whatsapp",
        destination="+56912345678",
        body="Morning brief: two meetings and a deadline today.",
    )

    assert notice.source_system == "whatsapp"
    assert notice.body

    with pytest.raises(IntegrationContractError, match="destination"):
        OutboundNotice(source_system="whatsapp", destination="", body="hi")
    with pytest.raises(IntegrationContractError, match="character limit"):
        OutboundNotice(
            source_system="whatsapp",
            destination="+56912345678",
            body="x" * (MAX_MESSAGE_CHARS + 1),
        )


def test_outbound_policy_refuses_an_unconfirmed_send() -> None:
    notice = OutboundNotice(
        source_system="whatsapp",
        destination="+56912345678",
        body="Morning brief: two meetings and a deadline today.",
    )
    policy = OutboundPolicy()

    with pytest.raises(OutboundConfirmationError, match="confirmation"):
        policy.assert_can_send(notice, confirmation=None)


def test_outbound_policy_sends_only_with_the_preview_digest() -> None:
    notice = OutboundNotice(
        source_system="whatsapp",
        destination="+56912345678",
        body="Morning brief: two meetings and a deadline today.",
    )
    policy = OutboundPolicy()

    with pytest.raises(OutboundConfirmationError, match="matches the preview"):
        policy.assert_can_send(notice, confirmation="wrong-token")

    policy.assert_can_send(
        notice,
        confirmation=outbound_preview_digest(notice),
    )


def test_outbound_preview_changes_when_the_message_changes() -> None:
    base = {
        "source_system": "whatsapp",
        "destination": "+56912345678",
    }
    first = OutboundNotice(body="Reminder: close the day", **base)
    second = OutboundNotice(body="Reminder: close the day now", **base)

    assert outbound_preview_digest(first) != outbound_preview_digest(second)


def test_outbound_policy_can_be_disabled_explicitly() -> None:
    notice = OutboundNotice(
        source_system="whatsapp",
        destination="+56912345678",
        body="hello",
    )
    OutboundPolicy(require_confirmation=False).assert_can_send(notice, confirmation=None)


def test_outbound_policy_bounds_are_validated() -> None:
    with pytest.raises(IntegrationContractError, match="max_message_chars"):
        OutboundPolicy(max_message_chars=0)


def test_receipt_keeps_a_stable_source_key() -> None:
    receipt = ExternalMessageReceipt(
        source_system="whatsapp",
        external_id="out-42",
        sent_at=datetime(2026, 9, 16, 9, 1, tzinfo=UTC),
    )

    assert receipt.source_key == ("whatsapp", "out-42")
    assert receipt.sent_at.tzinfo is UTC