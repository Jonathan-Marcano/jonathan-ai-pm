"""Integration retention and local disconnection, adapted to the unified model.

Retention deletes expired synchronization history (runs and their error rows) without touching
operational records. Disconnection removes provider identity links and reuse mappings for a
source system while preserving project, meeting, and deliverable records.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from faroflow.models import (
    ExternalIdentity,
    MeetingProjectMapping,
    SyncRun,
    SyncRunError,
    utc_now,
)


class IntegrationMaintenanceError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class RetentionResult:
    sync_runs_deleted: int
    sync_run_errors_deleted: int


@dataclass(frozen=True, slots=True)
class DisconnectionResult:
    source_system: str
    external_scope: str | None
    identities_deleted: int
    mappings_deleted: int
    sync_runs_anonymized: int
    sync_run_errors_deleted: int


def _as_utc(value: datetime | None, name: str) -> datetime:
    if value is None:
        return utc_now()
    if value.tzinfo is None:
        raise IntegrationMaintenanceError(f"{name} must carry a timezone")
    return value.astimezone(UTC)


def _positive_int(value: int, name: str) -> None:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise IntegrationMaintenanceError(f"{name} must be a positive integer")


class IntegrationMaintenanceService:
    """Apply retention and local disconnection without deleting operational records."""

    def __init__(self, session: Session):
        self.session = session

    def enforce_retention(
        self,
        *,
        sync_history_days: int,
        as_of: datetime | None = None,
    ) -> RetentionResult:
        _positive_int(sync_history_days, "sync_history_days")
        reference_time = _as_utc(as_of, "as_of")
        cutoff = (reference_time - timedelta(days=sync_history_days)).replace(tzinfo=None)

        old_run_ids = list(
            self.session.scalars(
                select(SyncRun.id).where(SyncRun.started_at < cutoff)
            )
        )
        errors_deleted = 0
        if old_run_ids:
            errors_deleted = self.session.execute(
                delete(SyncRunError)
                .where(SyncRunError.sync_run_id.in_(old_run_ids))
                .execution_options(synchronize_session=False)
            ).rowcount or 0
        runs_deleted = self.session.execute(
            delete(SyncRun)
            .where(SyncRun.started_at < cutoff)
            .execution_options(synchronize_session=False)
        ).rowcount or 0
        return RetentionResult(
            sync_runs_deleted=runs_deleted,
            sync_run_errors_deleted=errors_deleted,
        )

    def disconnect(
        self,
        source_system: str,
        *,
        external_scope: str | None = None,
    ) -> DisconnectionResult:
        source = source_system.strip().lower()
        if not source:
            raise IntegrationMaintenanceError("source_system is required")

        identity_filters = [ExternalIdentity.source_system == source]
        mapping_filters = [MeetingProjectMapping.source_system == source]
        if external_scope is not None:
            identity_filters.append(ExternalIdentity.external_scope == external_scope)
            mapping_filters.append(MeetingProjectMapping.external_scope == external_scope)

        identities_deleted = (
            self.session.execute(
                delete(ExternalIdentity)
                .where(*identity_filters)
                .execution_options(synchronize_session=False)
            ).rowcount
            or 0
        )
        mappings_deleted = (
            self.session.execute(
                delete(MeetingProjectMapping)
                .where(*mapping_filters)
                .execution_options(synchronize_session=False)
            ).rowcount
            or 0
        )

        run_ids = list(
            self.session.scalars(select(SyncRun.id).where(SyncRun.source_system == source))
        )
        errors_deleted = 0
        if run_ids:
            errors_deleted = self.session.execute(
                delete(SyncRunError)
                .where(SyncRunError.sync_run_id.in_(run_ids))
                .execution_options(synchronize_session=False)
            ).rowcount or 0
        anonymized = 0
        for run in self.session.scalars(
            select(SyncRun).where(SyncRun.source_system == source)
        ):
            run.source_system = "disconnected"
            if run.external_scope is not None:
                run.external_scope = None
            anonymized += 1

        return DisconnectionResult(
            source_system=source,
            external_scope=external_scope,
            identities_deleted=identities_deleted,
            mappings_deleted=mappings_deleted,
            sync_runs_anonymized=anonymized,
            sync_run_errors_deleted=errors_deleted,
        )