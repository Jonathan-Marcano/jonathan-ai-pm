from datetime import UTC, datetime, timedelta

import pytest

from faroflow.integrations.contracts import (
    READ_ONLY_CAPABILITIES,
    CalendarWindow,
    ExternalCalendarEvent,
)
from faroflow.integrations.persistence import IntegrationStateStore
from faroflow.integrations.reconciliation import reconcile_calendar_events
from faroflow.models import Meeting, MeetingProjectMapping
from faroflow.services import DomainRuleError, DomainStore

START = datetime(2026, 9, 15, 9, 0, tzinfo=UTC)
WINDOW = CalendarWindow(starts_at=START, ends_at=START + timedelta(days=30))


def build_project(session) -> None:
    store = DomainStore(session)
    store.create("workspace", id="wrk_demo", name="Demo", timezone="America/Santiago")
    store.create("client", id="cli_demo", workspace_id="wrk_demo", name="Demo client")
    store.create("project", id="prj_demo", client_id="cli_demo", name="Demo project")
    store.create("project", id="prj_other", client_id="cli_demo", name="Other project")


def event(
    external_id: str,
    *,
    title: str = "Standup",
    starts_at: datetime | None = None,
    status: str = "confirmed",
) -> ExternalCalendarEvent:
    return ExternalCalendarEvent(
        source_system="mocked-365",
        calendar_id="work-default",
        external_id=external_id,
        title=title,
        starts_at=starts_at or START,
        ends_at=(starts_at or START) + timedelta(hours=1),
        status=status,
        web_url=f"https://example.test/events/{external_id}",
        last_modified_at=START,
    )


class FakedAdapter:
    source_system = "mocked-365"
    capabilities = READ_ONLY_CAPABILITIES

    def __init__(self, events=None):
        self._events = list(events or [])

    def list_events(self, window: CalendarWindow) -> list[ExternalCalendarEvent]:
        return list(self._events)


def reconcile(session, adapter, *, project_id=None) -> object:
    return reconcile_calendar_events(
        session, project_id=project_id, adapter=adapter, window=WINDOW
    )


def review_meeting(session) -> Meeting:
    build_project(session)
    run = reconcile(session, FakedAdapter([event("evt-1")]))
    assert run.created_count == 1
    meeting = session.query(Meeting).one()
    assert meeting.project_id is None
    return meeting


def test_sync_without_project_creates_review_meeting(session) -> None:
    build_project(session)
    run = reconcile(session, FakedAdapter([event("evt-1")]))

    assert run.status == "succeeded"
    meeting = session.query(Meeting).one()
    assert meeting.project_id is None
    events, has_more = DomainStore(session).list_meetings_without_project(limit=10)
    assert [item.id for item in events] == [meeting.id]
    assert has_more is False


def test_review_queue_reports_in_progress_and_cancelled(session) -> None:
    build_project(session)
    adapter = FakedAdapter(
        [
            event("evt-1", title="One", starts_at=START),
            event("evt-2", title="Two", starts_at=START + timedelta(hours=2)),
            event("evt-3", title="Three", starts_at=START + timedelta(hours=1), status="cancelled"),
        ]
    )
    reconcile(session, adapter)

    events, _ = DomainStore(session).list_meetings_without_project()
    assert [item.title for item in events] == ["One", "Three", "Two"]
    assert [item.status for item in events] == ["scheduled", "cancelled", "scheduled"]


def test_confirm_project_records_reusable_mapping(session) -> None:
    meeting = review_meeting(session)
    store = DomainStore(session)

    associated = store.associate_meeting(meeting.id, "prj_demo")
    assert associated.project_id == "prj_demo"

    mapping = IntegrationStateStore(session).find_project_mapping(
        source_system="mocked-365", external_scope="work-default", external_id="evt-1"
    )
    assert mapping is not None
    assert mapping.project_id == "prj_demo"

    run = reconcile(session, FakedAdapter([event("evt-1")]))
    assert run.created_count == 0
    assert run.updated_count == 0
    assert run.unchanged_count == 1
    assert session.query(Meeting).count() == 1
    assert session.query(Meeting).one().project_id == "prj_demo"


def test_new_event_reuses_confirmed_mapping(session) -> None:
    build_project(session)
    IntegrationStateStore(session).set_project_mapping(
        source_system="mocked-365",
        external_scope="work-default",
        external_id="evt-1",
        project_id="prj_demo",
    )

    run = reconcile(session, FakedAdapter([event("evt-1")]))
    assert run.created_count == 1
    assert session.query(Meeting).one().project_id == "prj_demo"


def test_caller_project_is_recorded_and_reused(session) -> None:
    build_project(session)
    first = reconcile(session, FakedAdapter([event("evt-1")]), project_id="prj_demo")
    assert first.created_count == 1
    assert session.query(Meeting).one().project_id == "prj_demo"

    mapping = IntegrationStateStore(session).find_project_mapping(
        source_system="mocked-365", external_scope="work-default", external_id="evt-1"
    )
    assert mapping is not None
    assert mapping.project_id == "prj_demo"

    second = reconcile(session, FakedAdapter([event("evt-1")]))
    assert second.created_count == 0
    assert second.unchanged_count == 1
    assert session.query(Meeting).one().project_id == "prj_demo"


def test_sync_never_overrides_existing_association(session) -> None:
    build_project(session)
    reconcile(session, FakedAdapter([event("evt-1")]), project_id="prj_demo")

    run = reconcile(session, FakedAdapter([event("evt-1")]), project_id="prj_other")
    assert run.updated_count == 0
    assert run.unchanged_count == 1
    assert session.query(Meeting).one().project_id == "prj_demo"

    mapping = IntegrationStateStore(session).find_project_mapping(
        source_system="mocked-365", external_scope="work-default", external_id="evt-1"
    )
    assert mapping.project_id == "prj_demo"


def test_mapping_fills_previously_unmatched_meeting(session) -> None:
    meeting = review_meeting(session)
    IntegrationStateStore(session).set_project_mapping(
        source_system="mocked-365",
        external_scope="work-default",
        external_id="evt-1",
        project_id="prj_demo",
    )

    run = reconcile(session, FakedAdapter([event("evt-1")]))
    assert run.updated_count == 1
    assert session.get(Meeting, meeting.id).project_id == "prj_demo"


def test_deleting_mapping_keeps_operational_data(session) -> None:
    meeting = review_meeting(session)
    DomainStore(session).associate_meeting(meeting.id, "prj_demo")
    mapping = IntegrationStateStore(session).find_project_mapping(
        source_system="mocked-365", external_scope="work-default", external_id="evt-1"
    )
    assert mapping is not None

    IntegrationStateStore(session).delete_project_mapping(mapping.id)
    assert session.query(MeetingProjectMapping).count() == 0
    assert session.query(Meeting).one().project_id == "prj_demo"


def test_unmatched_meeting_cannot_create_tasks(session) -> None:
    meeting = review_meeting(session)
    DomainStore(session).create(
        "action_item",
        id="act_demo",
        meeting_id=meeting.id,
        title="Do a thing",
        status="captured",
        owner="Jonathan",
    )

    with pytest.raises(DomainRuleError, match="before creating tasks"):
        DomainStore(session).create_task_from_action("act_demo", "tsk_demo")


def test_unmatched_meeting_cannot_triage_actions(session) -> None:
    meeting = review_meeting(session)
    capture = DomainStore(session).capture("Remember the parking spot")

    with pytest.raises(DomainRuleError, match="before creating action items"):
        DomainStore(session).triage_capture(
            capture.id,
            "action",
            meeting_id=meeting.id,
            action_item_id="act_demo",
            owner="Jonathan",
        )


def test_api_review_queue_and_confirmation(api_client, session) -> None:
    review_meeting(session)

    queue = api_client.get("/api/v1/integrations/meetings/unmatched")
    assert queue.status_code == 200
    meeting = queue.json()[0]
    assert meeting["status"] == "scheduled"
    assert meeting["project_id"] is None

    confirmed = api_client.post(
        f"/api/v1/integrations/meetings/{meeting['id']}/project",
        json={"project_id": "prj_demo"},
    )
    assert confirmed.status_code == 200
    assert confirmed.json()["project_id"] == "prj_demo"

    mappings = api_client.get("/api/v1/integrations/meeting-project-mappings")
    assert mappings.status_code == 200
    assert len(mappings.json()) == 1
    assert mappings.json()[0]["project_id"] == "prj_demo"

    assert api_client.get("/api/v1/integrations/meetings/unmatched").json() == []


def test_api_confirm_project_404s(api_client, session) -> None:
    review_meeting(session)
    missing_meeting = api_client.post(
        "/api/v1/integrations/meetings/mtg_missing/project",
        json={"project_id": "prj_demo"},
    )
    assert missing_meeting.status_code == 404

    meeting = session.query(Meeting).one()
    missing_project = api_client.post(
        f"/api/v1/integrations/meetings/{meeting.id}/project",
        json={"project_id": "prj_missing"},
    )
    assert missing_project.status_code == 404


def test_api_pagination_for_review_queue(api_client, session) -> None:
    build_project(session)
    reconcile(
        session,
        FakedAdapter([event("evt-1", title="One"), event("evt-2", title="Two")]),
    )

    response = api_client.get("/api/v1/integrations/meetings/unmatched?limit=1")
    assert len(response.json()) == 1
    assert 'rel="next"' in response.headers.get("Link", "")


def test_api_delete_mapping_404(api_client, session) -> None:
    response = api_client.delete("/api/v1/integrations/meeting-project-mappings/map_missing")
    assert response.status_code == 404