"""P4-02: ingesta de mensajes entrantes hacia la bandeja (idempotente, sin auto-aplicar)."""

from datetime import UTC, datetime, timedelta

from faroflow.integrations import (
    READ_ONLY_CAPABILITIES,
    ExternalInboundMessage,
    IntegrationCapabilities,
)
from faroflow.integrations.reconciliation import ingest_inbound_messages
from faroflow.models import BandejaItem

SINCE = datetime(2026, 9, 1, tzinfo=UTC)


class FakeMessagingAdapter:
    source_system = "telegram"
    capabilities = READ_ONLY_CAPABILITIES

    def __init__(self, messages, *, fail=False):
        self.messages = messages
        self.fail = fail
        self.calls = []

    def list_messages(self, conversation_ids, since):
        self.calls.append((conversation_ids, since))
        if self.fail:
            raise RuntimeError("provider unavailable")
        return self.messages


class UnsafeMessagingAdapter(FakeMessagingAdapter):
    capabilities = IntegrationCapabilities(read=True, create=True, update=False, delete=False)


def message(external_id="a1", conversation_id="42", text="Meet the client", sender="Ana",
            received_at=None):
    return ExternalInboundMessage(
        source_system="telegram",
        conversation_id=conversation_id,
        external_id=external_id,
        text=text,
        received_at=received_at or SINCE + timedelta(hours=1),
        sender_display=sender,
    )


def test_ingest_creates_bandeja_capture_and_is_idempotent(session) -> None:
    adapter = FakeMessagingAdapter([message()])
    first = ingest_inbound_messages(
        session, adapter=adapter, conversation_ids=["42"], since=SINCE
    )
    assert first.status == "succeeded"
    assert first.seen_count == 1
    assert first.created_count == 1
    assert first.unchanged_count == 0

    captured = session.query(BandejaItem).all()
    assert len(captured) == 1
    assert captured[0].status == "received"
    assert captured[0].kind == "unknown"
    assert captured[0].destination_module is None
    assert captured[0].author == "Ana"
    assert captured[0].source_ref == "42:a1"

    second = ingest_inbound_messages(
        session, adapter=adapter, conversation_ids=["42"], since=SINCE
    )
    assert second.status == "succeeded"
    assert second.seen_count == 1
    assert second.unchanged_count == 1
    assert second.created_count == 0
    assert session.query(BandejaItem).count() == 1


def test_ingest_never_auto_applies_routing(session) -> None:
    ingest_inbound_messages(
        session, adapter=FakeMessagingAdapter([message()]), conversation_ids=["42"], since=SINCE
    )
    captured = session.query(BandejaItem).one()
    assert captured.channel == "telegram"
    assert captured.kind == "unknown"
    assert captured.project_id is None
    assert captured.habit_id is None
    from faroflow.models import Task

    assert session.query(Task).count() == 0


def test_ingest_unsupported_source_system_is_skipped(session) -> None:
    unsupported = ExternalInboundMessage(
        source_system="sms",
        conversation_id="42",
        external_id="a1",
        text="hola",
        received_at=SINCE + timedelta(hours=1),
    )
    run = ingest_inbound_messages(
        session, adapter=FakeMessagingAdapter([unsupported]), conversation_ids=["42"], since=SINCE
    )
    assert run.status == "partial"
    assert run.skipped_count == 1


def test_ingest_rejects_unsafe_adapter(session) -> None:
    run = ingest_inbound_messages(
        session,
        adapter=UnsafeMessagingAdapter([message()]),
        conversation_ids=["42"],
        since=SINCE,
    )
    assert run.status == "failed"
    assert session.query(BandejaItem).count() == 0


def test_ingest_records_provider_failure(session) -> None:
    run = ingest_inbound_messages(
        session,
        adapter=FakeMessagingAdapter([], fail=True),
        conversation_ids=["42"],
        since=SINCE,
    )
    assert run.status == "failed"
    assert run.seen_count == 0


def test_messaging_inbound_endpoint_returns_503_when_unconfigured(api_client) -> None:
    response = api_client.post(
        "/api/v1/integrations/messaging/inbound",
        params={"conversation_ids": ["42"], "since": "2026-09-01T00:00:00Z"},
    )
    assert response.status_code == 503
    assert "not configured" in response.json()["detail"]