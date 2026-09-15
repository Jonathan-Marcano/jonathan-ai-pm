from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from hashlib import sha256

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

import jonathan_ai_pm.audit  # noqa: F401
from jonathan_ai_pm.integrations.contracts import CalendarWindow, ExternalCalendarEvent
from jonathan_ai_pm.integrations.persistence import IntegrationStateStore
from jonathan_ai_pm.models import ExternalIdentity, Meeting, Project, utc_now


class CalendarReconciliationError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class CalendarReconciliationResult:
    run_id: str
    status: str
    seen_count: int
    created_count: int
    updated_count: int
    unchanged_count: int
    skipped_count: int
    error_count: int
    missing_identity_ids: tuple[str, ...]


class CalendarReconciler:
    """Reconcile one bounded provider calendar view without guessing project ownership."""

    def __init__(self, session: Session):
        self.session = session
        self.state = IntegrationStateStore(session)

    def reconcile(
        self,
        events: Sequence[ExternalCalendarEvent],
        *,
        window: CalendarWindow,
        source_system: str,
        external_scope: str,
        project_ids: Mapping[str, str] | None = None,
        synced_at: datetime | None = None,
    ) -> CalendarReconciliationResult:
        source_system = _required_text(source_system, "source_system").lower()
        external_scope = _required_text(external_scope, "external_scope")
        synced_at = _as_utc(synced_at or utc_now(), "synced_at")
        project_ids = project_ids or {}
        run = self.state.start_run(
            source_system=source_system,
            resource_kind="calendar",
            external_scope=external_scope,
            window_starts_at=window.starts_at,
            window_ends_at=window.ends_at,
            started_at=synced_at,
        )

        unique_events: dict[tuple[str, str, str], ExternalCalendarEvent] = {}
        duplicate_count = 0
        for event in events:
            if event.source_key in unique_events:
                duplicate_count += 1
            unique_events[event.source_key] = event

        counts = {
            "created": 0,
            "updated": 0,
            "unchanged": 0,
            "skipped": duplicate_count,
        }
        seen_source_keys: set[tuple[str, str, str]] = set()
        for event in unique_events.values():
            if event.source_system == source_system and event.calendar_id == external_scope:
                seen_source_keys.add(event.source_key)
            try:
                outcome = self._reconcile_event(
                    event,
                    window=window,
                    source_system=source_system,
                    external_scope=external_scope,
                    project_id=project_ids.get(event.external_id),
                    synced_at=synced_at,
                )
                counts[outcome] += 1
            except (CalendarReconciliationError, SQLAlchemyError) as exc:
                self.session.rollback()
                counts["skipped"] += 1
                message = (
                    str(exc)
                    if isinstance(exc, CalendarReconciliationError)
                    else "Calendar event could not be persisted"
                )
                self.state.record_error(
                    run.id,
                    code="calendar_reconciliation_error",
                    message=message,
                    occurred_at=synced_at,
                )

        missing_identity_ids = self._mark_missing(
            window=window,
            source_system=source_system,
            external_scope=external_scope,
            seen_source_keys=seen_source_keys,
            synced_at=synced_at,
        )
        completed = self.state.finish_run(
            run.id,
            seen_count=len(events),
            created_count=counts["created"],
            updated_count=counts["updated"],
            unchanged_count=counts["unchanged"],
            skipped_count=counts["skipped"],
            completed_at=synced_at,
        )
        return CalendarReconciliationResult(
            run_id=completed.id,
            status=completed.status,
            seen_count=completed.seen_count,
            created_count=completed.created_count,
            updated_count=completed.updated_count,
            unchanged_count=completed.unchanged_count,
            skipped_count=completed.skipped_count,
            error_count=completed.error_count,
            missing_identity_ids=missing_identity_ids,
        )

    def _reconcile_event(
        self,
        event: ExternalCalendarEvent,
        *,
        window: CalendarWindow,
        source_system: str,
        external_scope: str,
        project_id: str | None,
        synced_at: datetime,
    ) -> str:
        if event.source_system != source_system or event.calendar_id != external_scope:
            raise CalendarReconciliationError(
                "Calendar event does not match the synchronization source"
            )
        if event.status not in {"confirmed", "cancelled"}:
            raise CalendarReconciliationError("Calendar event has an unsupported status")
        if event.ends_at <= window.starts_at or event.starts_at >= window.ends_at:
            raise CalendarReconciliationError(
                "Calendar event is outside the synchronization window"
            )

        identity = self.session.scalar(
            select(ExternalIdentity).where(
                ExternalIdentity.source_system == source_system,
                ExternalIdentity.external_scope == external_scope,
                ExternalIdentity.external_id == event.external_id,
            )
        )
        if identity is None:
            if not project_id:
                return "skipped"
            if self.session.get(Project, project_id) is None:
                raise CalendarReconciliationError("Mapped project does not exist")
            meeting = Meeting(
                id=_meeting_id(event.source_key),
                project_id=project_id,
                title=event.title,
                starts_at=event.starts_at,
                status="cancelled" if event.status == "cancelled" else "scheduled",
            )
            identity = ExternalIdentity(
                id=_identity_id(event.source_key),
                entity_kind="meeting",
                entity_id=meeting.id,
                source_system=source_system,
                external_scope=external_scope,
                external_id=event.external_id,
                external_version=_event_version(event),
                web_url=event.web_url,
                external_modified_at=event.last_modified_at,
                last_synced_at=synced_at,
                missing_since=None,
            )
            self.session.add_all([meeting, identity])
            self.session.commit()
            return "created"

        if identity.entity_kind != "meeting":
            raise CalendarReconciliationError("Calendar identity is not linked to a meeting")
        meeting = self.session.get(Meeting, identity.entity_id)
        if meeting is None:
            raise CalendarReconciliationError("Calendar identity points to a missing meeting")

        target_status = "cancelled" if event.status == "cancelled" else "scheduled"
        if meeting.status == "completed":
            target_status = "completed"
        changed = any(
            (
                meeting.title != event.title,
                not _same_instant(meeting.starts_at, event.starts_at),
                meeting.status != target_status,
                identity.external_version != _event_version(event),
                identity.web_url != event.web_url,
                not _same_optional_instant(
                    identity.external_modified_at, event.last_modified_at
                ),
                identity.missing_since is not None,
            )
        )
        meeting.title = event.title
        meeting.starts_at = event.starts_at
        meeting.status = target_status
        identity.external_version = _event_version(event)
        identity.web_url = event.web_url
        identity.external_modified_at = event.last_modified_at
        identity.last_synced_at = synced_at
        identity.missing_since = None
        self.session.commit()
        return "updated" if changed else "unchanged"

    def _mark_missing(
        self,
        *,
        window: CalendarWindow,
        source_system: str,
        external_scope: str,
        seen_source_keys: set[tuple[str, str, str]],
        synced_at: datetime,
    ) -> tuple[str, ...]:
        statement = (
            select(ExternalIdentity)
            .join(
                Meeting,
                (ExternalIdentity.entity_kind == "meeting")
                & (ExternalIdentity.entity_id == Meeting.id),
            )
            .where(
                ExternalIdentity.source_system == source_system,
                ExternalIdentity.external_scope == external_scope,
                Meeting.starts_at >= window.starts_at,
                Meeting.starts_at < window.ends_at,
            )
            .order_by(ExternalIdentity.id)
        )
        missing = [
            identity
            for identity in self.session.scalars(statement)
            if (
                identity.source_system,
                identity.external_scope,
                identity.external_id,
            )
            not in seen_source_keys
        ]
        for identity in missing:
            if identity.missing_since is None:
                identity.missing_since = synced_at
        if missing:
            self.session.commit()
        return tuple(identity.id for identity in missing)


def _meeting_id(source_key: tuple[str, str, str]) -> str:
    return f"mtg_ext_{_source_digest(source_key)}"


def _identity_id(source_key: tuple[str, str, str]) -> str:
    return f"ext_{_source_digest(source_key)}"


def _source_digest(source_key: tuple[str, str, str]) -> str:
    return sha256("\0".join(source_key).encode()).hexdigest()[:24]


def _event_version(event: ExternalCalendarEvent) -> str | None:
    return event.last_modified_at.isoformat() if event.last_modified_at else None


def _required_text(value: str, field_name: str) -> str:
    normalized = value.strip()
    if not normalized:
        raise CalendarReconciliationError(f"{field_name} cannot be empty")
    return normalized


def _as_utc(value: datetime, field_name: str) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise CalendarReconciliationError(f"{field_name} must include a timezone")
    return value.astimezone(UTC)


def _stored_as_utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _same_instant(left: datetime, right: datetime) -> bool:
    return _stored_as_utc(left) == _stored_as_utc(right)


def _same_optional_instant(left: datetime | None, right: datetime | None) -> bool:
    if left is None or right is None:
        return left is right
    return _same_instant(left, right)
