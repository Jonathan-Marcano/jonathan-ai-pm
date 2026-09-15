from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select

from jonathan_ai_pm.integrations import (
    CalendarAssociationError,
    CalendarAssociationService,
    CalendarReconciler,
    CalendarWindow,
    ExternalCalendarEvent,
)
from jonathan_ai_pm.models import (
    CalendarImportReview,
    CalendarProjectMapping,
    ExternalIdentity,
    Meeting,
)
from jonathan_ai_pm.services import DomainStore

SOURCE = "microsoft-365"
SCOPE = "work-a:default"
SYNCED_AT = datetime(2026, 9, 15, 9, 0, tzinfo=UTC)


def build_projects(session) -> None:
    store = DomainStore(session)
    store.create("workspace", id="wrk_demo", name="Demo", timezone="America/Santiago")
    store.create("client", id="cli_demo", workspace_id="wrk_demo", name="Demo client")
    store.create("project", id="prj_one", client_id="cli_demo", name="Client review")
    store.create("project", id="prj_two", client_id="cli_demo", name="Other project")


def window() -> CalendarWindow:
    return CalendarWindow(
        starts_at=datetime(2026, 9, 15, 0, 0, tzinfo=UTC),
        ends_at=datetime(2026, 9, 22, 0, 0, tzinfo=UTC),
    )


def event(
    *,
    external_id: str = "event-123",
    title: str = "Client review",
    starts_at: datetime = datetime(2026, 9, 15, 16, 0, tzinfo=UTC),
    scope: str = SCOPE,
) -> ExternalCalendarEvent:
    return ExternalCalendarEvent(
        source_system=SOURCE,
        calendar_id=scope,
        external_id=external_id,
        title=title,
        starts_at=starts_at,
        ends_at=starts_at + timedelta(hours=1),
        status="confirmed",
        web_url=f"https://outlook.office.com/calendar/item/{external_id}",
        last_modified_at=SYNCED_AT,
    )


def reconcile(session, events, *, scope=SCOPE, synced_at=SYNCED_AT):
    return CalendarReconciler(session).reconcile(
        events,
        window=window(),
        source_system=SOURCE,
        external_scope=scope,
        synced_at=synced_at,
    )


def test_unmatched_event_enters_review_queue_without_title_guessing(session) -> None:
    build_projects(session)
    result = reconcile(session, [event()])

    review = session.scalar(select(CalendarImportReview))
    assert result.skipped_count == 1
    assert result.queued_review_ids == (review.id,)
    assert review.status == "pending"
    assert review.title == "Client review"
    assert review.resolution_project_id is None
    assert session.query(Meeting).count() == 0
    assert CalendarAssociationService(session).list_pending() == [review]


def test_repeated_unmatched_event_updates_one_review_item(session) -> None:
    build_projects(session)
    first = reconcile(session, [event()])
    later = SYNCED_AT + timedelta(hours=2)
    moved = event(
        title="Renamed client review",
        starts_at=datetime(2026, 9, 16, 18, 0, tzinfo=UTC),
    )

    second = reconcile(session, [moved], synced_at=later)
    review = session.scalar(select(CalendarImportReview))

    assert first.queued_review_ids == second.queued_review_ids
    assert session.query(CalendarImportReview).count() == 1
    assert review.title == "Renamed client review"
    assert review.starts_at.replace(tzinfo=UTC) == moved.starts_at
    assert review.last_seen_at.replace(tzinfo=UTC) == later


def test_confirmed_mapping_is_reused_by_future_reconciliation(session) -> None:
    build_projects(session)
    queued = reconcile(session, [event()])
    review_id = queued.queued_review_ids[0]
    associations = CalendarAssociationService(session)

    mapping = associations.confirm(
        review_id,
        project_id="prj_two",
        actor="jonathan",
        confirmed_at=SYNCED_AT + timedelta(minutes=5),
    )
    imported = reconcile(session, [event()], synced_at=SYNCED_AT + timedelta(minutes=10))
    repeated = reconcile(session, [event()], synced_at=SYNCED_AT + timedelta(minutes=15))

    review = session.get(CalendarImportReview, review_id)
    meeting = session.scalar(select(Meeting))
    assert mapping.project_id == "prj_two"
    assert mapping.confirmed_by == "jonathan"
    assert review.status == "resolved"
    assert review.resolution_project_id == "prj_two"
    assert imported.created_count == 1
    assert repeated.unchanged_count == 1
    assert meeting.project_id == "prj_two"
    assert session.query(Meeting).count() == 1
    assert session.query(ExternalIdentity).count() == 1


def test_mapping_source_key_is_scoped_to_one_calendar(session) -> None:
    build_projects(session)
    first = event(scope="work-a:default")
    reconcile(session, [first], scope="work-a:default")
    review = session.scalar(select(CalendarImportReview))
    CalendarAssociationService(session).confirm(
        review.id, project_id="prj_one", actor="jonathan"
    )

    other = event(scope="work-b:default")
    result = reconcile(session, [other], scope="work-b:default")

    assert result.skipped_count == 1
    assert result.created_count == 0
    assert session.query(CalendarImportReview).count() == 2
    assert session.query(CalendarProjectMapping).count() == 1


def test_dismissed_review_stays_out_of_pending_queue_when_event_reappears(session) -> None:
    build_projects(session)
    result = reconcile(session, [event()])
    associations = CalendarAssociationService(session)
    review = associations.dismiss(
        result.queued_review_ids[0],
        actor="jonathan",
        dismissed_at=SYNCED_AT + timedelta(minutes=5),
    )

    reconcile(session, [event(title="Updated title")], synced_at=SYNCED_AT + timedelta(hours=1))
    session.refresh(review)

    assert review.status == "dismissed"
    assert review.title == "Updated title"
    assert associations.list_pending() == []
    assert session.query(Meeting).count() == 0


def test_confirmation_requires_existing_project(session) -> None:
    build_projects(session)
    result = reconcile(session, [event()])

    with pytest.raises(CalendarAssociationError, match="Project not found"):
        CalendarAssociationService(session).confirm(
            result.queued_review_ids[0],
            project_id="prj_missing",
            actor="jonathan",
        )


def test_imported_meeting_cannot_be_reassigned_by_changing_mapping(session) -> None:
    build_projects(session)
    result = reconcile(session, [event()])
    associations = CalendarAssociationService(session)
    associations.confirm(result.queued_review_ids[0], project_id="prj_one", actor="jonathan")
    reconcile(session, [event()], synced_at=SYNCED_AT + timedelta(minutes=5))

    with pytest.raises(CalendarAssociationError, match="cannot be reassigned"):
        associations.confirm(
            result.queued_review_ids[0],
            project_id="prj_two",
            actor="jonathan",
        )

    assert session.scalar(select(Meeting.project_id)) == "prj_one"
