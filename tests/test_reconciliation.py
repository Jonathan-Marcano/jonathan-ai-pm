from datetime import UTC, datetime, timedelta

import pytest

from faroflow.integrations.contracts import (
    READ_ONLY_CAPABILITIES,
    CalendarWindow,
    ExternalCalendarEvent,
)
from faroflow.integrations.persistence import IntegrationStateError
from faroflow.integrations.reconciliation import reconcile_calendar_events
from faroflow.models import ExternalIdentity, Meeting, SyncRun, SyncRunError
from faroflow.services import DomainStore

START = datetime(2026, 9, 15, 9, 0, tzinfo=UTC)
WINDOW = CalendarWindow(starts_at=START, ends_at=START + timedelta(days=30))


def build_project(session) -> None:
    store = DomainStore(session)
    store.create("workspace", id="wrk_demo", name="Demo", timezone="America/Santiago")
    store.create("client", id="cli_demo", workspace_id="wrk_demo", name="Demo client")
    store.create("project", id="prj_demo", client_id="cli_demo", name="Demo project")


def event(
    external_id: str,
    *,
    title: str = "Standup",
    status: str = "confirmed",
    clock_offset_minutes: int = 0,
    last_modified_minutes: int = 0,
) -> ExternalCalendarEvent:
    return ExternalCalendarEvent(
        source_system="mocked-365",
        calendar_id="work-default",
        external_id=external_id,
        title=title,
        starts_at=START + timedelta(minutes=clock_offset_minutes),
        ends_at=START + timedelta(minutes=clock_offset_minutes, hours=1),
        status=status,
        web_url=f"https://example.test/events/{external_id}",
        last_modified_at=START + timedelta(minutes=last_modified_minutes),
    )


class FakedAdapter:
    source_system = "mocked-365"
    capabilities = READ_ONLY_CAPABILITIES

    def __init__(self, events=None, error: Exception | None = None):
        self._events = list(events or [])
        self._error = error
        self.calls = 0

    def list_events(self, window: CalendarWindow) -> list[ExternalCalendarEvent]:
        self.calls += 1
        if self._error is not None:
            raise self._error
        return list(self._events)


def reconcile(session, adapter, window: CalendarWindow = WINDOW) -> SyncRun:
    return reconcile_calendar_events(
        session, project_id="prj_demo", adapter=adapter, window=window
    )


def test_first_sync_creates_meetings_and_identities(session) -> None:
    build_project(session)
    run = reconcile(
        session,
        FakedAdapter([event("evt-1"), event("evt-2", clock_offset_minutes=30)]),
    )

    assert run.status == "succeeded"
    assert run.seen_count == 2
    assert run.created_count == 2
    assert run.updated_count == 0
    assert run.unchanged_count == 0

    meetings = session.query(Meeting).order_by(Meeting.title).all()
    assert [meeting.title for meeting in meetings] == ["Standup", "Standup"]
    assert all(meeting.project_id == "prj_demo" for meeting in meetings)
    assert session.query(ExternalIdentity).count() == 2
    assert session.query(SyncRun).count() == 1


def test_repeated_sync_never_duplicates(session) -> None:
    build_project(session)
    events = [event("evt-1", last_modified_minutes=10)]
    adapter = FakedAdapter(events)
    first_run = reconcile(session, adapter)
    assert first_run.created_count == 1

    second_run = reconcile(session, adapter)
    assert second_run.status == "succeeded"
    assert second_run.created_count == 0
    assert second_run.updated_count == 0
    assert second_run.unchanged_count == 1
    assert session.query(Meeting).count() == 1
    assert session.query(ExternalIdentity).count() == 1


def test_changed_event_updates_the_same_meeting(session) -> None:
    build_project(session)
    adapter = FakedAdapter([event("evt-1")])
    reconcile(session, adapter)

    adapter = FakedAdapter(
        [event("evt-1", title="Standup renamed", clock_offset_minutes=15)]
    )
    run = reconcile(session, adapter)

    assert run.created_count == 0
    assert run.updated_count == 1
    assert session.query(Meeting).count() == 1
    meeting = session.query(Meeting).one()
    assert meeting.title == "Standup renamed"
    assert meeting.starts_at.replace(tzinfo=UTC) == START + timedelta(minutes=15)


def test_cancelled_event_marks_meeting_cancelled(session) -> None:
    build_project(session)
    reconcile(session, FakedAdapter([event("evt-1")]))
    run = reconcile(session, FakedAdapter([event("evt-1", status="cancelled")]))

    assert run.updated_count == 1
    assert session.query(Meeting).one().status == "cancelled"


def test_cancellation_never_reopens_settled_meeting(session) -> None:
    build_project(session)
    store = DomainStore(session)
    reconcile(session, FakedAdapter([event("evt-1")]))
    store.update("meeting", session.query(Meeting).one().id, status="completed")

    run = reconcile(session, FakedAdapter([event("evt-1", status="cancelled")]))
    assert run.updated_count == 0
    assert run.unchanged_count == 1
    assert session.query(Meeting).one().status == "completed"


def test_cancelled_event_creates_cancelled_meeting_on_first_sync(session) -> None:
    build_project(session)
    run = reconcile(session, FakedAdapter([event("evt-1", status="cancelled")]))
    assert run.created_count == 1
    assert session.query(Meeting).one().status == "cancelled"


def test_missing_events_never_delete_meetings(session) -> None:
    build_project(session)
    reconcile(session, FakedAdapter([event("evt-1"), event("evt-2")]))
    run = reconcile(session, FakedAdapter([event("evt-1")]))

    assert run.seen_count == 1
    assert session.query(Meeting).count() == 2
    assert session.query(ExternalIdentity).count() == 2


def test_failed_listing_records_error_and_finishes_failed(session) -> None:
    build_project(session)
    adapter = FakedAdapter(error=RuntimeError("token unavailable"))

    run = reconcile(session, adapter)
    assert run.status == "failed"
    assert run.seen_count == 0
    assert run.error_count == 1
    assert session.query(SyncRunError).count() == 1
    assert "token" in session.query(SyncRunError).one().message


def test_project_is_required(session) -> None:
    with pytest.raises(IntegrationStateError, match="project not found"):
        reconcile_calendar_events(
            session, project_id="prj_missing", adapter=FakedAdapter(), window=WINDOW
        )