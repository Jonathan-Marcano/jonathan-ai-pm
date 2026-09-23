from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from faroflow.integrations.contracts import (
    CalendarWindow,
    ExternalCalendarEvent,
    ExternalDocumentMetadata,
    ReadOnlyCalendarAdapter,
    ReadOnlyDocumentAdapter,
)
from faroflow.integrations.messaging import ExternalInboundMessage
from faroflow.integrations.persistence import IntegrationStateError, IntegrationStateStore
from faroflow.integrations.safety import (
    ProviderSafetyError,
    check_messaging_adapter,
    check_read_only_adapter,
)
from faroflow.models import (
    BandejaItem,
    Deliverable,
    ExternalIdentity,
    Meeting,
    Project,
    SyncRun,
)
from faroflow.services import DomainRuleError, DomainStore
from faroflow.unified import InboxService

_MESSAGING_CHANNELS = {"telegram", "whatsapp"}

CANCELLED_EVENT_STATUS = "cancelled"
CANCELLED_MEETING_STATUS = "cancelled"
SETTLED_MEETING_STATUSES = {"cancelled", "completed"}


def reconcile_calendar_events(
    session: Session,
    *,
    project_id: str | None = None,
    adapter: ReadOnlyCalendarAdapter,
    window: CalendarWindow,
    started_at: datetime | None = None,
) -> SyncRun:
    """Reconcile read-only calendar events into meetings idempotently.

    Deduplication uses the stable source key ``source_system + calendar_id + external_id``.
    Repeated syncs update the linked meeting, cancellations mark it cancelled without reopening
    settled records, and events missing from a window never delete operational data.

    Meetings created without a confirmed project enter the review queue (``project_id`` is null)
    and are associated through user-confirmed mappings that later syncs reuse. Explicit caller
    ``project_id`` values are authoritative for new or unmatched meetings and never override an
    already-associated meeting.
    """
    if project_id is not None and session.get(Project, project_id) is None:
        raise IntegrationStateError(f"project not found: {project_id}")

    state = IntegrationStateStore(session)
    store = DomainStore(session)
    run = state.start_run(
        source_system=adapter.source_system,
        resource_kind="calendar",
        window_starts_at=window.starts_at,
        window_ends_at=window.ends_at,
        started_at=started_at,
    )

    try:
        check_read_only_adapter(adapter)
        events = adapter.list_events(window)
    except Exception as exc:
        state.record_error(
            run.id,
            code="unsafe_adapter" if isinstance(exc, ProviderSafetyError) else "list_failed",
            message=str(exc) or "Calendar listing failed",
        )
        return state.finish_run(run.id, seen_count=0, status="failed")

    created = updated = unchanged = skipped = 0
    for event in events:
        try:
            outcome = _reconcile_event(
                session, state, store, project_id=project_id, event=event
            )
        except (DomainRuleError, IntegrationStateError) as exc:
            session.rollback()
            state.record_error(run.id, code="reconcile_failed", message=str(exc))
            skipped += 1
            continue
        if outcome == "created":
            created += 1
        elif outcome == "updated":
            updated += 1
        else:
            unchanged += 1

    return state.finish_run(
        run.id,
        seen_count=len(events),
        created_count=created,
        updated_count=updated,
        unchanged_count=unchanged,
        skipped_count=skipped,
    )


def _resolve_project(
    state: IntegrationStateStore,
    explicit_project_id: str | None,
    event: ExternalCalendarEvent,
) -> str | None:
    if explicit_project_id is not None:
        return explicit_project_id
    mapping = state.find_project_mapping(
        source_system=event.source_system,
        external_scope=event.calendar_id,
        external_id=event.external_id,
    )
    return mapping.project_id if mapping is not None else None


def _reconcile_event(
    session: Session,
    state: IntegrationStateStore,
    store: DomainStore,
    *,
    project_id: str | None,
    event: ExternalCalendarEvent,
) -> str:
    identity = state.find_identity(
        source_system=event.source_system,
        external_scope=event.calendar_id,
        external_id=event.external_id,
    )
    if identity is None:
        return _create_meeting(session, state, store, project_id=project_id, event=event)

    meeting = session.get(Meeting, identity.entity_id)
    if meeting is None:
        raise IntegrationStateError(
            f"External identity references a missing meeting: {identity.entity_id}"
        )
    resolved_project = _resolve_project(state, project_id, event)
    changes = _meeting_changes(meeting, event, resolved_project)
    if changes:
        store.update("meeting", meeting.id, **changes)
        if "project_id" in changes:
            state.set_project_mapping(
                source_system=event.source_system,
                external_scope=event.calendar_id,
                external_id=event.external_id,
                project_id=resolved_project,
            )
        _refresh_identity(state, identity, event)
        return "updated"
    _refresh_identity(state, identity, event)
    return "unchanged"


def _create_meeting(
    session: Session,
    state: IntegrationStateStore,
    store: DomainStore,
    *,
    project_id: str | None,
    event: ExternalCalendarEvent,
) -> str:
    resolved_project = _resolve_project(state, project_id, event)
    meeting = store.create(
        "meeting",
        id=f"mtg_{uuid4().hex}",
        project_id=resolved_project,
        title=event.title,
        starts_at=event.starts_at,
        status=(
            CANCELLED_MEETING_STATUS
            if event.status == CANCELLED_EVENT_STATUS
            else "scheduled"
        ),
    )
    if resolved_project is not None:
        state.set_project_mapping(
            source_system=event.source_system,
            external_scope=event.calendar_id,
            external_id=event.external_id,
            project_id=resolved_project,
        )
    state.upsert_identity(
        entity_kind="meeting",
        entity_id=meeting.id,
        source_system=event.source_system,
        external_id=event.external_id,
        external_scope=event.calendar_id,
        web_url=event.web_url,
        external_modified_at=event.last_modified_at,
    )
    return "created"


def _meeting_changes(
    meeting: Meeting,
    event: ExternalCalendarEvent,
    resolved_project: str | None,
) -> dict[str, object]:
    changes: dict[str, object] = {}
    if meeting.title != event.title:
        changes["title"] = event.title
    if _as_utc(meeting.starts_at) != event.starts_at:
        changes["starts_at"] = event.starts_at
    if meeting.project_id is None and resolved_project is not None:
        changes["project_id"] = resolved_project
    if (
        event.status == CANCELLED_EVENT_STATUS
        and meeting.status not in SETTLED_MEETING_STATUSES
    ):
        changes["status"] = CANCELLED_MEETING_STATUS
    return changes


def _refresh_identity(
    state: IntegrationStateStore,
    identity: ExternalIdentity,
    event: ExternalCalendarEvent,
) -> None:
    state.upsert_identity(
        entity_kind="meeting",
        entity_id=identity.entity_id,
        source_system=event.source_system,
        external_id=event.external_id,
        external_scope=event.calendar_id,
        web_url=event.web_url,
        external_modified_at=event.last_modified_at,
    )


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def reconcile_drive_files(
    session: Session,
    *,
    adapter: ReadOnlyDocumentAdapter,
    external_ids: list[str] | None = None,
    started_at: datetime | None = None,
) -> SyncRun:
    """Refresh Drive link metadata for linked deliverables idempotently.

    Only deliverables already linked to the provider are refreshed; unknown file ids are
    ignored, document bodies are never copied, and the external file is never modified or
    deleted. Name, URL, MIME type, version marker, and modification time are updated in place.
    """
    state = IntegrationStateStore(session)
    store = DomainStore(session)
    run = state.start_run(
        source_system=adapter.source_system,
        resource_kind="document",
        started_at=started_at,
    )

    try:
        check_read_only_adapter(adapter)
    except Exception as exc:
        state.record_error(
            run.id,
            code="unsafe_adapter",
            message=str(exc) or "Drive adapter declared unsafe",
        )
        return state.finish_run(run.id, seen_count=0, status="failed")

    identities, _ = state.list_deliverable_identities(source_system=adapter.source_system)
    requested = {value.strip() for value in external_ids} if external_ids else None
    if requested is not None:
        identities = [item for item in identities if item.external_id in requested]

    updated = unchanged = 0
    for identity in identities:
        try:
            metadata = adapter.get_metadata(identity.external_id)
        except Exception as exc:
            session.rollback()
            state.record_error(
                run.id,
                code="metadata_failed",
                message=str(exc) or "Drive metadata refresh failed",
                external_identity_id=identity.id,
            )
            continue
        try:
            outcome = _reconcile_drive_file(session, state, store, identity, metadata)
        except (DomainRuleError, IntegrationStateError) as exc:
            session.rollback()
            state.record_error(
                run.id,
                code="reconcile_failed",
                message=str(exc),
                external_identity_id=identity.id,
            )
            continue
        if outcome == "updated":
            updated += 1
        else:
            unchanged += 1

    return state.finish_run(
        run.id,
        seen_count=len(identities),
        created_count=0,
        updated_count=updated,
        unchanged_count=unchanged,
        skipped_count=max(len(identities) - updated - unchanged, 0),
    )


def _reconcile_drive_file(
    session: Session,
    state: IntegrationStateStore,
    store: DomainStore,
    identity: ExternalIdentity,
    metadata: ExternalDocumentMetadata,
) -> str:
    deliverable = session.get(Deliverable, identity.entity_id)
    if deliverable is None:
        raise IntegrationStateError(
            f"External identity references a missing deliverable: {identity.entity_id}"
        )
    if (
        metadata.source_system != identity.source_system
        or metadata.external_id != identity.external_id
    ):
        raise IntegrationStateError(
            "Drive metadata does not match the linked external identity"
        )

    metadata_changed = (
        identity.external_name != metadata.name
        or identity.web_url != metadata.web_url
        or identity.mime_type != metadata.mime_type
        or identity.external_version != metadata.etag
        or not _same_modified(identity.external_modified_at, metadata.last_modified_at)
    )
    state.upsert_identity(
        entity_kind="deliverable",
        entity_id=identity.entity_id,
        source_system=metadata.source_system,
        external_id=metadata.external_id,
        external_scope=identity.external_scope,
        external_version=metadata.etag,
        external_name=metadata.name,
        mime_type=metadata.mime_type,
        web_url=metadata.web_url,
        external_modified_at=metadata.last_modified_at,
    )
    drive_url_changed = (
        metadata.web_url is not None and deliverable.drive_url != metadata.web_url
    )
    if drive_url_changed:
        store.update("deliverable", deliverable.id, drive_url=metadata.web_url)
    return "updated" if metadata_changed or drive_url_changed else "unchanged"


def _same_modified(existing: datetime | None, fresh: datetime | None) -> bool:
    if existing is None or fresh is None:
        return existing is None and fresh is None
    return _as_utc(existing) == _as_utc(fresh)


def ingest_inbound_messages(
    session: Session,
    *,
    adapter,
    conversation_ids: list[str],
    since: datetime,
    started_at: datetime | None = None,
) -> SyncRun:
    """Reconcile bounded messaging messages into inbox captures idempotently (P4-02).

    Inbound messages become ``BandejaItem`` records with a stable source key derived from
    ``source_system + conversation_id + external_id``. Repeated polls return the same key and
    update nothing instead of duplicating the capture, and messages are never applied to a
    project or habit on their own.
    """
    state = IntegrationStateStore(session)
    inbox = InboxService(session)
    run = state.start_run(
        source_system=adapter.source_system,
        resource_kind="message",
        external_scope=",".join(sorted(conversation_ids)) or None,
        started_at=started_at,
    )

    try:
        check_messaging_adapter(adapter)
        messages = adapter.list_messages(conversation_ids, _as_utc(since))
    except Exception as exc:
        state.record_error(
            run.id,
            code="unsafe_adapter" if isinstance(exc, ProviderSafetyError) else "list_failed",
            message=str(exc) or "Messaging inbound listing failed",
        )
        return state.finish_run(run.id, seen_count=0, status="failed")

    created = duplicated = skipped = 0
    for message in messages:
        try:
            outcome = _ingest_message(session, inbox, state, run.id, message)
        except IntegrationStateError as exc:
            session.rollback()
            state.record_error(run.id, code="ingest_failed", message=str(exc))
            skipped += 1
            continue
        if outcome == "created":
            created += 1
        else:
            duplicated += 1

    return state.finish_run(
        run.id,
        seen_count=len(messages),
        created_count=created,
        updated_count=0,
        unchanged_count=duplicated,
        skipped_count=skipped,
    )


def _ingest_message(
    session: Session,
    inbox: InboxService,
    state: IntegrationStateStore,
    run_id: str,
    message: ExternalInboundMessage,
) -> str:
    channel = _messaging_channel(message.source_system)
    source_ref = f"{message.conversation_id}:{message.external_id}"[:240]
    exists = session.scalar(
        select(BandejaItem.id).where(
            BandejaItem.channel == channel,
            BandejaItem.source_ref == source_ref,
        )
    )
    inbox.receive(
        channel=channel,
        source_ref=source_ref,
        original_text=message.text,
        author=message.sender_display,
        original_at=message.received_at,
    )
    return "created" if exists is None else "unchanged"


def _messaging_channel(source_system: str) -> str:
    channel = source_system.strip().lower()
    if channel not in _MESSAGING_CHANNELS:
        raise IntegrationStateError(f"Unsupported messaging source system: {source_system}")
    return channel