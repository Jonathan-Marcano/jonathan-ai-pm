from datetime import UTC, datetime, timedelta

from sqlalchemy import select

from jonathan_ai_pm.integrations import (
    CalendarReconciler,
    CalendarWindow,
    ExternalCalendarEvent,
    IntegrationStateStore,
)
from jonathan_ai_pm.models import ExternalIdentity, Meeting, SyncRun
from jonathan_ai_pm.services import DomainStore

SOURCE = "microsoft-365"
SCOPE = "work-a:default"
SYNCED_AT = datetime(2026, 9, 15, 9, 0, tzinfo=UTC)


def build_project(session) -> None:
    store = DomainStore(session)
    store.create("workspace", id="wrk_demo", name="Demo", timezone="America/Santiago")
    store.create("client", id="cli_demo", workspace_id="wrk_demo", name="Demo client")
    store.create("project", id="prj_demo", client_id="cli_demo", name="Demo project")


def window() -> CalendarWindow:
    return CalendarWindow(
        starts_at=datetime(2026, 9, 15, 0, 0, tzinfo=UTC),
        ends_at=datetime(2026, 9, 22, 0, 0, tzinfo=UTC),
    )


def event(
    *,
    external_id="event-123",
    title="Client review",
    starts_at=datetime(2026, 9, 15, 16, 0, tzinfo=UTC),
    status="confirmed",
    modified_at=datetime(2026, 9, 15, 8, 0, tzinfo=UTC),
) -> ExternalCalendarEvent:
    return ExternalCalendarEvent(
        source_system=SOURCE,
        calendar_id=SCOPE,
        external_id=external_id,
        title=title,
        starts_at=starts_at,
        ends_at=starts_at + timedelta(hours=1),
        status=status,
        web_url=f"https://outlook.office.com/calendar/item/{external_id}",
        last_modified_at=modified_at,
    )


def reconcile(session, events, project_ids=None, synced_at=SYNCED_AT):
    return CalendarReconciler(session).reconcile(
        events,
        window=window(),
        source_system=SOURCE,
        external_scope=SCOPE,
        project_ids=project_ids,
        synced_at=synced_at,
    )


def test_first_reconciliation_creates_one_meeting_and_identity(session) -> None:
    build_project(session)
    result = reconcile(session, [event()], {"event-123": "prj_demo"})

    meetings = list(session.scalars(select(Meeting)))
    identities = list(session.scalars(select(ExternalIdentity)))
    assert result.status == "succeeded"
    assert result.created_count == 1
    assert len(meetings) == 1
    assert len(identities) == 1
    assert identities[0].entity_id == meetings[0].id
    assert identities[0].external_id == "event-123"
    assert identities[0].missing_since is None


def test_repeating_same_window_is_idempotent(session) -> None:
    build_project(session)
    first = reconcile(session, [event()], {"event-123": "prj_demo"})
    meeting_id = session.scalar(select(Meeting.id))
    second = reconcile(session, [event()], {"event-123": "prj_demo"})

    assert first.created_count == 1
    assert second.unchanged_count == 1
    assert second.created_count == 0
    assert session.query(Meeting).count() == 1
    assert session.query(ExternalIdentity).count() == 1
    assert session.scalar(select(Meeting.id)) == meeting_id


def test_renamed_or_rescheduled_event_updates_same_meeting(session) -> None:
    build_project(session)
    reconcile(session, [event()], {"event-123": "prj_demo"})
    original_id = session.scalar(select(Meeting.id))
    changed = event(
        title="Updated client review",
        starts_at=datetime(2026, 9, 16, 18, 0, tzinfo=UTC),
        modified_at=datetime(2026, 9, 15, 10, 0, tzinfo=UTC),
    )

    result = reconcile(session, [changed], synced_at=SYNCED_AT + timedelta(hours=2))
    meeting = session.get(Meeting, original_id)

    assert result.updated_count == 1
    assert session.query(Meeting).count() == 1
    assert meeting.title == "Updated client review"
    assert meeting.starts_at.replace(tzinfo=UTC) == changed.starts_at


def test_explicit_cancellation_is_applied_but_completed_meeting_is_preserved(session) -> None:
    build_project(session)
    reconcile(session, [event()], {"event-123": "prj_demo"})
    cancelled = event(status="cancelled", modified_at=SYNCED_AT + timedelta(hours=1))
    result = reconcile(session, [cancelled], synced_at=SYNCED_AT + timedelta(hours=1))
    meeting = session.scalar(select(Meeting))

    assert result.updated_count == 1
    assert meeting.status == "cancelled"

    meeting.status = "completed"
    session.commit()
    reconcile(session, [cancelled], synced_at=SYNCED_AT + timedelta(hours=2))
    assert session.get(Meeting, meeting.id).status == "completed"


def test_missing_event_is_flagged_without_deleting_or_cancelling(session) -> None:
    build_project(session)
    reconcile(session, [event()], {"event-123": "prj_demo"})
    identity = session.scalar(select(ExternalIdentity))
    meeting = session.scalar(select(Meeting))

    missing = reconcile(session, [], synced_at=SYNCED_AT + timedelta(hours=1))
    session.refresh(identity)
    session.refresh(meeting)

    assert missing.missing_identity_ids == (identity.id,)
    assert identity.missing_since is not None
    assert meeting.status == "scheduled"
    assert session.get(Meeting, meeting.id) is meeting

    reappeared = reconcile(session, [event()], synced_at=SYNCED_AT + timedelta(hours=2))
    session.refresh(identity)
    assert reappeared.updated_count == 1
    assert identity.missing_since is None


def test_unmapped_new_event_is_skipped_without_guessing_project(session) -> None:
    build_project(session)
    result = reconcile(session, [event()])

    assert result.status == "succeeded"
    assert result.skipped_count == 1
    assert session.query(Meeting).count() == 0
    assert session.query(ExternalIdentity).count() == 0


def test_event_outside_window_is_rejected_and_audited(session) -> None:
    build_project(session)
    outside = event(starts_at=datetime(2026, 9, 23, 16, 0, tzinfo=UTC))
    result = reconcile(session, [outside], {"event-123": "prj_demo"})

    assert result.status == "partial"
    assert result.error_count == 1
    assert result.skipped_count == 1
    assert session.query(Meeting).count() == 0


def test_duplicate_provider_items_do_not_create_duplicate_meetings(session) -> None:
    build_project(session)
    result = reconcile(
        session,
        [event(title="First title"), event(title="Last title")],
        {"event-123": "prj_demo"},
    )

    assert result.seen_count == 2
    assert result.created_count == 1
    assert result.skipped_count == 1
    assert session.query(Meeting).count() == 1
    assert session.scalar(select(Meeting.title)) == "Last title"


def test_broken_identity_records_error_and_partial_run(session) -> None:
    build_project(session)
    meeting = DomainStore(session).create(
        "meeting",
        id="mtg_demo",
        project_id="prj_demo",
        title="Client review",
        starts_at=datetime(2026, 9, 15, 16, 0, tzinfo=UTC),
    )
    IntegrationStateStore(session).upsert_identity(
        entity_kind="meeting",
        entity_id=meeting.id,
        source_system=SOURCE,
        external_scope=SCOPE,
        external_id="event-123",
    )
    session.delete(meeting)
    session.commit()

    result = reconcile(session, [event()])
    run = session.get(SyncRun, result.run_id)

    assert result.status == "partial"
    assert result.error_count == 1
    assert result.skipped_count == 1
    assert run.error_count == 1
    assert result.missing_identity_ids == ()
