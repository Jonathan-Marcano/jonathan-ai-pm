from __future__ import annotations

from datetime import UTC, datetime
from hashlib import sha256

from sqlalchemy import select
from sqlalchemy.orm import Session

from jonathan_ai_pm.integrations.contracts import ExternalCalendarEvent
from jonathan_ai_pm.models import (
    CalendarImportReview,
    CalendarProjectMapping,
    ExternalIdentity,
    Meeting,
    Project,
    utc_now,
)


class CalendarAssociationError(ValueError):
    pass


class CalendarAssociationService:
    """Persist explicit calendar-to-project decisions without content-based guessing."""

    def __init__(self, session: Session):
        self.session = session

    def project_id_for(self, source_key: tuple[str, str, str]) -> str | None:
        mapping = self.session.scalar(
            select(CalendarProjectMapping).where(
                CalendarProjectMapping.source_system == source_key[0],
                CalendarProjectMapping.external_scope == source_key[1],
                CalendarProjectMapping.external_id == source_key[2],
            )
        )
        return mapping.project_id if mapping else None

    def queue_unmatched(
        self,
        event: ExternalCalendarEvent,
        *,
        seen_at: datetime | None = None,
    ) -> CalendarImportReview:
        seen_at = _as_utc(seen_at or utc_now(), "seen_at")
        review = self.session.scalar(
            select(CalendarImportReview).where(
                CalendarImportReview.source_system == event.source_system,
                CalendarImportReview.external_scope == event.calendar_id,
                CalendarImportReview.external_id == event.external_id,
            )
        )
        if review is None:
            review = CalendarImportReview(
                id=_review_id(event.source_key),
                source_system=event.source_system,
                external_scope=event.calendar_id,
                external_id=event.external_id,
                title=event.title,
                starts_at=event.starts_at,
                ends_at=event.ends_at,
                event_status=event.status,
                web_url=event.web_url,
                external_modified_at=event.last_modified_at,
                status="pending",
                first_seen_at=seen_at,
                last_seen_at=seen_at,
                resolution_project_id=None,
                resolved_by=None,
                resolved_at=None,
            )
            self.session.add(review)
        else:
            review.title = event.title
            review.starts_at = event.starts_at
            review.ends_at = event.ends_at
            review.event_status = event.status
            review.web_url = event.web_url
            review.external_modified_at = event.last_modified_at
            review.last_seen_at = seen_at
        self.session.commit()
        self.session.refresh(review)
        return review

    def list_pending(
        self,
        *,
        source_system: str | None = None,
        external_scope: str | None = None,
    ) -> list[CalendarImportReview]:
        statement = select(CalendarImportReview).where(CalendarImportReview.status == "pending")
        if source_system is not None:
            statement = statement.where(
                CalendarImportReview.source_system
                == _required_text(source_system, "source_system").lower()
            )
        if external_scope is not None:
            statement = statement.where(
                CalendarImportReview.external_scope
                == _required_text(external_scope, "external_scope")
            )
        return list(
            self.session.scalars(
                statement.order_by(CalendarImportReview.starts_at, CalendarImportReview.id)
            )
        )

    def confirm(
        self,
        review_id: str,
        *,
        project_id: str,
        actor: str,
        confirmed_at: datetime | None = None,
    ) -> CalendarProjectMapping:
        review = self._review(review_id)
        project_id = _required_text(project_id, "project_id")
        actor = _required_text(actor, "actor")[:200]
        confirmed_at = _as_utc(confirmed_at or utc_now(), "confirmed_at")
        if self.session.get(Project, project_id) is None:
            raise CalendarAssociationError(f"Project not found: {project_id}")

        source_key = (review.source_system, review.external_scope, review.external_id)
        identity = self._identity(source_key)
        if identity is not None:
            meeting = self.session.get(Meeting, identity.entity_id)
            if meeting is None or meeting.project_id != project_id:
                raise CalendarAssociationError(
                    "An imported meeting cannot be reassigned through a calendar mapping"
                )

        mapping = self.session.scalar(
            select(CalendarProjectMapping).where(
                CalendarProjectMapping.source_system == review.source_system,
                CalendarProjectMapping.external_scope == review.external_scope,
                CalendarProjectMapping.external_id == review.external_id,
            )
        )
        if mapping is None:
            mapping = CalendarProjectMapping(
                id=_mapping_id(source_key),
                source_system=review.source_system,
                external_scope=review.external_scope,
                external_id=review.external_id,
                project_id=project_id,
                confirmed_by=actor,
                confirmed_at=confirmed_at,
            )
            self.session.add(mapping)
        else:
            mapping.project_id = project_id
            mapping.confirmed_by = actor
            mapping.confirmed_at = confirmed_at

        review.status = "resolved"
        review.resolution_project_id = project_id
        review.resolved_by = actor
        review.resolved_at = confirmed_at
        self.session.commit()
        self.session.refresh(mapping)
        return mapping

    def dismiss(
        self,
        review_id: str,
        *,
        actor: str,
        dismissed_at: datetime | None = None,
    ) -> CalendarImportReview:
        review = self._review(review_id)
        review.status = "dismissed"
        review.resolution_project_id = None
        review.resolved_by = _required_text(actor, "actor")[:200]
        review.resolved_at = _as_utc(dismissed_at or utc_now(), "dismissed_at")
        self.session.commit()
        self.session.refresh(review)
        return review

    def _review(self, review_id: str) -> CalendarImportReview:
        review = self.session.get(
            CalendarImportReview, _required_text(review_id, "review_id")
        )
        if review is None:
            raise CalendarAssociationError(f"Calendar review not found: {review_id}")
        return review

    def _identity(
        self, source_key: tuple[str, str, str]
    ) -> ExternalIdentity | None:
        return self.session.scalar(
            select(ExternalIdentity).where(
                ExternalIdentity.source_system == source_key[0],
                ExternalIdentity.external_scope == source_key[1],
                ExternalIdentity.external_id == source_key[2],
            )
        )


def _review_id(source_key: tuple[str, str, str]) -> str:
    return f"calrev_{_source_digest(source_key)}"


def _mapping_id(source_key: tuple[str, str, str]) -> str:
    return f"calmap_{_source_digest(source_key)}"


def _source_digest(source_key: tuple[str, str, str]) -> str:
    return sha256("\0".join(source_key).encode()).hexdigest()[:24]


def _required_text(value: str, field_name: str) -> str:
    normalized = value.strip()
    if not normalized:
        raise CalendarAssociationError(f"{field_name} cannot be empty")
    return normalized


def _as_utc(value: datetime, field_name: str) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise CalendarAssociationError(f"{field_name} must include a timezone")
    return value.astimezone(UTC)
