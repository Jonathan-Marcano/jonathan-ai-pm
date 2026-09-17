from datetime import UTC, datetime, timedelta

import pytest

from faroflow.integrations.contracts import (
    READ_ONLY_CAPABILITIES,
    CalendarWindow,
    ExternalCalendarEvent,
    ExternalDocumentMetadata,
    IntegrationCapabilities,
)
from faroflow.integrations.persistence import IntegrationStateStore
from faroflow.integrations.reconciliation import (
    reconcile_calendar_events,
    reconcile_drive_files,
)
from faroflow.integrations.safety import (
    ProviderSafetyError,
    assert_registered_providers_read_only,
    check_scope_read_only,
)
from faroflow.models import Meeting
from faroflow.services import DomainRuleError, DomainStore

START = datetime(2026, 9, 17, 9, 0, tzinfo=UTC)
WINDOW = CalendarWindow(starts_at=START, ends_at=START + timedelta(days=7))

WRITE_CAPABILITIES = IntegrationCapabilities(
    read=True, create=True, update=True, delete=True
)


def build_project(session) -> None:
    store = DomainStore(session)
    store.create("workspace", id="wrk_demo", name="Demo", timezone="America/Santiago")
    store.create("client", id="cli_demo", workspace_id="wrk_demo", name="Demo client")
    store.create("project", id="prj_demo", client_id="cli_demo", name="Demo project")
    store.create(
        "deliverable",
        id="dlv_demo",
        project_id="prj_demo",
        title="Project plan",
        due_at=datetime(2026, 9, 30, tzinfo=UTC).date(),
    )


class WriteCalendarAdapter:
    source_system = "write-calendar"
    capabilities = WRITE_CAPABILITIES

    def list_events(self, window: CalendarWindow) -> list[ExternalCalendarEvent]:
        raise AssertionError("write adapter must not be called")


class WriteScopeCalendarAdapter:
    source_system = "write-scope"
    capabilities = READ_ONLY_CAPABILITIES
    delegated_scope = "https://www.googleapis.com/auth/calendar.readwrite"

    def list_events(self, window: CalendarWindow) -> list[ExternalCalendarEvent]:
        raise AssertionError("write-scope adapter must not be called")


class WriteDriveAdapter:
    source_system = "google-drive"
    capabilities = WRITE_CAPABILITIES

    def get_metadata(self, external_id: str) -> ExternalDocumentMetadata:
        raise AssertionError("write adapter must not be called")


def test_registered_providers_are_read_only() -> None:
    checks = assert_registered_providers_read_only()

    assert len(checks) == 3
    assert {check.source_system for check in checks} == {
        "microsoft-365",
        "google-calendar",
        "google-drive",
    }


def test_write_scope_is_rejected() -> None:
    with pytest.raises(ProviderSafetyError, match="write scope"):
        check_scope_read_only("calendar.readwrite", "mock")


def test_write_capabilities_are_rejected_at_sync_time() -> None:
    from faroflow.integrations.safety import check_read_only_adapter

    with pytest.raises(ProviderSafetyError, match="write capabilities"):
        check_read_only_adapter(WriteCalendarAdapter())


def test_calendar_sync_rejects_write_capable_adapter(session) -> None:
    build_project(session)

    run = reconcile_calendar_events(
        session, project_id="prj_demo", adapter=WriteCalendarAdapter(), window=WINDOW
    )

    assert run.status == "failed"
    assert session.query(Meeting).count() == 0
    errors = IntegrationStateStore(session).list_errors(run.id)
    assert errors[0].code == "unsafe_adapter"
    assert "write capabilities" in errors[0].message


def test_calendar_sync_rejects_write_scope(session) -> None:
    build_project(session)

    run = reconcile_calendar_events(
        session, project_id="prj_demo", adapter=WriteScopeCalendarAdapter(), window=WINDOW
    )

    assert run.status == "failed"
    errors = IntegrationStateStore(session).list_errors(run.id)
    assert errors[0].code == "unsafe_adapter"


def test_drive_sync_rejects_write_capable_adapter(session) -> None:
    build_project(session)

    run = reconcile_drive_files(session, adapter=WriteDriveAdapter())

    assert run.status == "failed"
    errors = IntegrationStateStore(session).list_errors(run.id)
    assert errors[0].code == "unsafe_adapter"


def test_linked_deliverable_cannot_be_deleted_before_unlinking(session) -> None:
    build_project(session)
    store = DomainStore(session)
    store.link_drive_file(
        "dlv_demo",
        source_system="google-drive",
        external_id="file-1",
        name="Plan.pdf",
        web_url="https://drive.example.test/file-1",
    )

    with pytest.raises(DomainRuleError, match="Unlink Drive files"):
        store.delete("deliverable", "dlv_demo")

    store.unlink_drive_file("dlv_demo")
    store.delete("deliverable", "dlv_demo")
    assert DomainStore(session).get("deliverable", "dlv_demo") is None