from datetime import UTC, datetime, timedelta

import pytest

from jonathan_ai_pm.integrations import (
    READ_ONLY_CAPABILITIES,
    CalendarWindow,
    ExternalCalendarEvent,
    ExternalDocumentMetadata,
    IntegrationContractError,
)


def test_calendar_window_normalizes_to_utc() -> None:
    offset = UTC + timedelta(0)
    window = CalendarWindow(
        starts_at=datetime(2026, 9, 15, 9, 0, tzinfo=offset),
        ends_at=datetime(2026, 9, 15, 10, 0, tzinfo=offset),
    )
    assert window.starts_at.tzinfo is UTC
    assert window.ends_at.tzinfo is UTC


def test_calendar_event_identity_does_not_depend_on_title() -> None:
    base = {
        "source_system": "Microsoft-365",
        "calendar_id": "work",
        "external_id": "event-123",
        "starts_at": datetime(2026, 9, 15, 13, 0, tzinfo=UTC),
        "ends_at": datetime(2026, 9, 15, 14, 0, tzinfo=UTC),
    }
    original = ExternalCalendarEvent(title="Weekly review", **base)
    renamed = ExternalCalendarEvent(title="Project review", **base)

    assert original.source_key == ("microsoft-365", "work", "event-123")
    assert renamed.source_key == original.source_key


def test_contract_rejects_naive_or_reversed_calendar_times() -> None:
    with pytest.raises(IntegrationContractError, match="timezone"):
        CalendarWindow(
            starts_at=datetime(2026, 9, 15, 9, 0),
            ends_at=datetime(2026, 9, 15, 10, 0, tzinfo=UTC),
        )
    with pytest.raises(IntegrationContractError, match="end after"):
        ExternalCalendarEvent(
            source_system="microsoft-365",
            calendar_id="work",
            external_id="event-123",
            title="Review",
            starts_at=datetime(2026, 9, 15, 14, 0, tzinfo=UTC),
            ends_at=datetime(2026, 9, 15, 13, 0, tzinfo=UTC),
        )


def test_document_identity_survives_metadata_changes() -> None:
    first = ExternalDocumentMetadata(
        source_system="google-drive",
        external_id="file-123",
        name="MOP draft",
        web_url="https://drive.google.com/file/d/file-123",
    )
    renamed = ExternalDocumentMetadata(
        source_system="google-drive",
        external_id="file-123",
        name="MOP approved",
        web_url="https://drive.google.com/file/d/file-123",
    )
    assert first.source_key == renamed.source_key == ("google-drive", "file-123")


def test_phase_2_contract_is_strictly_read_only() -> None:
    assert READ_ONLY_CAPABILITIES.read is True
    assert READ_ONLY_CAPABILITIES.create is False
    assert READ_ONLY_CAPABILITIES.update is False
    assert READ_ONLY_CAPABILITIES.delete is False
