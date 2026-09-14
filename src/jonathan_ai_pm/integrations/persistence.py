from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from jonathan_ai_pm.models import (
    MODEL_BY_KIND,
    ExternalIdentity,
    SyncRun,
    SyncRunError,
    utc_now,
)
from jonathan_ai_pm.security import redact_text


class IntegrationStateError(ValueError):
    pass


def _required_text(value: str, field_name: str) -> str:
    normalized = value.strip()
    if not normalized:
        raise IntegrationStateError(f"{field_name} cannot be empty")
    return normalized


def _optional_text(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip()
    return normalized or None


def _as_utc(value: datetime, field_name: str) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise IntegrationStateError(f"{field_name} must include a timezone")
    return value.astimezone(UTC)


def _stored_as_utc(value: datetime) -> datetime:
    """Restore UTC for backends such as SQLite that discard timezone metadata."""
    if value.tzinfo is None or value.utcoffset() is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


class IntegrationStateStore:
    """Transaction boundary for external identities and synchronization history."""

    def __init__(self, session: Session):
        self.session = session

    def upsert_identity(
        self,
        *,
        entity_kind: str,
        entity_id: str,
        source_system: str,
        external_id: str,
        external_scope: str = "",
        external_version: str | None = None,
        web_url: str | None = None,
        external_modified_at: datetime | None = None,
        synced_at: datetime | None = None,
    ) -> ExternalIdentity:
        if entity_kind not in {"meeting", "deliverable"}:
            raise IntegrationStateError("External identities support meetings and deliverables")
        target = self.session.get(MODEL_BY_KIND[entity_kind], entity_id)
        if target is None:
            raise IntegrationStateError(f"{entity_kind} not found: {entity_id}")

        source_system = _required_text(source_system, "source_system").lower()
        external_id = _required_text(external_id, "external_id")
        external_scope = external_scope.strip()
        synced_at = _as_utc(synced_at or utc_now(), "synced_at")
        if external_modified_at is not None:
            external_modified_at = _as_utc(external_modified_at, "external_modified_at")

        statement = select(ExternalIdentity).where(
            ExternalIdentity.source_system == source_system,
            ExternalIdentity.external_scope == external_scope,
            ExternalIdentity.external_id == external_id,
        )
        identity = self.session.scalar(statement)
        if identity is not None:
            if identity.entity_kind != entity_kind or identity.entity_id != entity_id:
                raise IntegrationStateError("External identity is already linked to another entity")
            identity.external_version = _optional_text(external_version)
            identity.web_url = _optional_text(web_url)
            identity.external_modified_at = external_modified_at
            identity.last_synced_at = synced_at
        else:
            identity = ExternalIdentity(
                id=f"ext_{uuid4().hex}",
                entity_kind=entity_kind,
                entity_id=entity_id,
                source_system=source_system,
                external_scope=external_scope,
                external_id=external_id,
                external_version=_optional_text(external_version),
                web_url=_optional_text(web_url),
                external_modified_at=external_modified_at,
                last_synced_at=synced_at,
            )
            self.session.add(identity)
        self.session.commit()
        self.session.refresh(identity)
        return identity

    def start_run(
        self,
        *,
        source_system: str,
        resource_kind: str,
        external_scope: str | None = None,
        window_starts_at: datetime | None = None,
        window_ends_at: datetime | None = None,
        started_at: datetime | None = None,
    ) -> SyncRun:
        source_system = _required_text(source_system, "source_system").lower()
        if resource_kind not in {"calendar", "document"}:
            raise IntegrationStateError(f"Unsupported resource kind: {resource_kind}")
        if (window_starts_at is None) != (window_ends_at is None):
            raise IntegrationStateError("Synchronization windows require both timestamps")
        if window_starts_at is not None and window_ends_at is not None:
            window_starts_at = _as_utc(window_starts_at, "window_starts_at")
            window_ends_at = _as_utc(window_ends_at, "window_ends_at")
            if window_starts_at >= window_ends_at:
                raise IntegrationStateError("Synchronization window must end after it starts")

        run = SyncRun(
            id=f"syn_{uuid4().hex}",
            source_system=source_system,
            resource_kind=resource_kind,
            external_scope=_optional_text(external_scope),
            status="running",
            window_starts_at=window_starts_at,
            window_ends_at=window_ends_at,
            started_at=_as_utc(started_at or utc_now(), "started_at"),
        )
        self.session.add(run)
        self.session.commit()
        self.session.refresh(run)
        return run

    def record_error(
        self,
        run_id: str,
        *,
        code: str,
        message: str,
        external_identity_id: str | None = None,
        occurred_at: datetime | None = None,
    ) -> SyncRunError:
        run = self._running(run_id)
        if (
            external_identity_id
            and self.session.get(ExternalIdentity, external_identity_id) is None
        ):
            raise IntegrationStateError(f"External identity not found: {external_identity_id}")
        safe_message = redact_text(_required_text(message, "message"))
        error = SyncRunError(
            id=f"err_{uuid4().hex}",
            sync_run_id=run.id,
            external_identity_id=external_identity_id,
            code=_required_text(code, "code").lower()[:100],
            message=safe_message,
            occurred_at=_as_utc(occurred_at or utc_now(), "occurred_at"),
        )
        run.error_count += 1
        self.session.add(error)
        self.session.commit()
        self.session.refresh(error)
        return error

    def finish_run(
        self,
        run_id: str,
        *,
        seen_count: int,
        created_count: int = 0,
        updated_count: int = 0,
        unchanged_count: int = 0,
        skipped_count: int = 0,
        status: str | None = None,
        completed_at: datetime | None = None,
    ) -> SyncRun:
        run = self._running(run_id)
        counts = {
            "seen_count": seen_count,
            "created_count": created_count,
            "updated_count": updated_count,
            "unchanged_count": unchanged_count,
            "skipped_count": skipped_count,
        }
        invalid_count = any(
            not isinstance(value, int) or isinstance(value, bool) or value < 0
            for value in counts.values()
        )
        if invalid_count:
            raise IntegrationStateError(
                "Synchronization outcome counts must be non-negative integers"
            )
        classified_count = created_count + updated_count + unchanged_count + skipped_count
        if classified_count != seen_count:
            raise IntegrationStateError("Synchronization outcome counts must add up to seen_count")

        if status is None:
            status = "partial" if run.error_count else "succeeded"
        if status not in {"succeeded", "partial", "failed"}:
            raise IntegrationStateError(f"Invalid completed status: {status}")
        if status == "succeeded" and run.error_count:
            raise IntegrationStateError("A synchronization with errors cannot succeed")
        if status == "partial" and not run.error_count:
            raise IntegrationStateError("A partial synchronization requires a recorded error")

        normalized_completed_at = _as_utc(completed_at or utc_now(), "completed_at")
        if normalized_completed_at < _stored_as_utc(run.started_at):
            raise IntegrationStateError("completed_at cannot be before started_at")
        for name, value in counts.items():
            setattr(run, name, value)
        run.status = status
        run.completed_at = normalized_completed_at
        self.session.commit()
        self.session.refresh(run)
        return run

    def list_errors(self, run_id: str) -> list[SyncRunError]:
        if self.session.get(SyncRun, run_id) is None:
            raise IntegrationStateError(f"Synchronization run not found: {run_id}")
        statement = select(SyncRunError).where(SyncRunError.sync_run_id == run_id).order_by(
            SyncRunError.occurred_at, SyncRunError.id
        )
        return list(self.session.scalars(statement))

    def _running(self, run_id: str) -> SyncRun:
        run = self.session.get(SyncRun, run_id)
        if run is None:
            raise IntegrationStateError(f"Synchronization run not found: {run_id}")
        if run.status != "running":
            raise IntegrationStateError("Synchronization run is already completed")
        return run
