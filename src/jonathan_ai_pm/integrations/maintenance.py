from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, update
from sqlalchemy.orm import Session

from jonathan_ai_pm.models import (
    CalendarImportReview,
    CalendarProjectMapping,
    ExternalIdentity,
    SyncRun,
    utc_now,
)


class IntegrationMaintenanceError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class RetentionResult:
    sync_runs_deleted: int
    resolved_reviews_deleted: int


@dataclass(frozen=True, slots=True)
class DisconnectionResult:
    source_system: str
    external_scope: str | None
    identities_deleted: int
    reviews_deleted: int
    mappings_deleted: int
    sync_runs_anonymized: int


class IntegrationMaintenanceService:
    """Apply retention and local disconnection without deleting operational records."""

    def __init__(self, session: Session):
        self.session = session

    def enforce_retention(
        self,
        *,
        sync_history_days: int,
        resolved_review_days: int,
        as_of: datetime | None = None,
    ) -> RetentionResult:
        if isinstance(sync_history_days, bool) or sync_history_days < 1:
            raise IntegrationMaintenanceError("sync_history_days must be positive")
        if isinstance(resolved_review_days, bool) or resolved_review_days < 1:
            raise IntegrationMaintenanceError("resolved_review_days must be positive")
        reference_time = _as_utc(as_of or utc_now(), "as_of")
        sync_cutoff = reference_time - timedelta(days=sync_history_days)
        review_cutoff = reference_time - timedelta(days=resolved_review_days)

        sync_result = self.session.execute(
            delete(SyncRun).where(
                SyncRun.status != "running",
                SyncRun.completed_at.is_not(None),
                SyncRun.completed_at < sync_cutoff,
            )
        )
        review_result = self.session.execute(
            delete(CalendarImportReview).where(
                CalendarImportReview.status.in_(("resolved", "dismissed")),
                CalendarImportReview.resolved_at.is_not(None),
                CalendarImportReview.resolved_at < review_cutoff,
            )
        )
        self.session.commit()
        return RetentionResult(
            sync_runs_deleted=sync_result.rowcount or 0,
            resolved_reviews_deleted=review_result.rowcount or 0,
        )

    def disconnect(
        self,
        source_system: str,
        *,
        external_scope: str | None = None,
    ) -> DisconnectionResult:
        source_system = _required_text(source_system, "source_system").lower()
        normalized_scope = (
            _required_text(external_scope, "external_scope") if external_scope is not None else None
        )

        identity_filter = [ExternalIdentity.source_system == source_system]
        review_filter = [CalendarImportReview.source_system == source_system]
        mapping_filter = [CalendarProjectMapping.source_system == source_system]
        run_filter = [SyncRun.source_system == source_system]
        if normalized_scope is not None:
            identity_filter.append(ExternalIdentity.external_scope == normalized_scope)
            review_filter.append(CalendarImportReview.external_scope == normalized_scope)
            mapping_filter.append(CalendarProjectMapping.external_scope == normalized_scope)
            run_filter.append(SyncRun.external_scope == normalized_scope)

        identity_result = self.session.execute(delete(ExternalIdentity).where(*identity_filter))
        review_result = self.session.execute(delete(CalendarImportReview).where(*review_filter))
        mapping_result = self.session.execute(delete(CalendarProjectMapping).where(*mapping_filter))
        run_result = self.session.execute(
            update(SyncRun)
            .where(*run_filter, SyncRun.external_scope.is_not(None))
            .values(external_scope=None)
        )
        self.session.commit()
        return DisconnectionResult(
            source_system=source_system,
            external_scope=normalized_scope,
            identities_deleted=identity_result.rowcount or 0,
            reviews_deleted=review_result.rowcount or 0,
            mappings_deleted=mapping_result.rowcount or 0,
            sync_runs_anonymized=run_result.rowcount or 0,
        )


def _required_text(value: str, field_name: str) -> str:
    normalized = value.strip()
    if not normalized:
        raise IntegrationMaintenanceError(f"{field_name} cannot be empty")
    return normalized


def _as_utc(value: datetime, field_name: str) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise IntegrationMaintenanceError(f"{field_name} must include a timezone")
    return value.astimezone(UTC)
