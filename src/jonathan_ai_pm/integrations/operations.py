from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import Session

from jonathan_ai_pm.integrations.contracts import (
    CalendarWindow,
    IntegrationContractError,
    ReadOnlyCalendarAdapter,
)
from jonathan_ai_pm.integrations.persistence import IntegrationStateStore
from jonathan_ai_pm.integrations.reconciliation import (
    CalendarReconciler,
    CalendarReconciliationResult,
)
from jonathan_ai_pm.integrations.security import require_read_only_capabilities
from jonathan_ai_pm.models import SyncRun, utc_now


class CalendarOperationError(ValueError):
    def __init__(self, message: str, *, run_id: str | None = None):
        super().__init__(message)
        self.run_id = run_id


@dataclass(frozen=True, slots=True)
class CalendarAdapterBinding:
    source_system: str
    external_scope: str
    adapter: ReadOnlyCalendarAdapter


class CalendarAdapterRegistry:
    """In-memory adapter registry; credentials remain inside deployment-owned providers."""

    def __init__(self) -> None:
        self._bindings: dict[tuple[str, str], CalendarAdapterBinding] = {}

    def register(
        self,
        *,
        source_system: str,
        external_scope: str,
        adapter: ReadOnlyCalendarAdapter,
    ) -> None:
        source_system = _required_text(source_system, "source_system").lower()
        external_scope = _required_text(external_scope, "external_scope")
        adapter_source = _required_text(adapter.source_system, "adapter.source_system").lower()
        if adapter_source != source_system:
            raise CalendarOperationError("Adapter source does not match its registry binding")
        require_read_only_capabilities(adapter.capabilities)
        self._bindings[(source_system, external_scope)] = CalendarAdapterBinding(
            source_system=source_system,
            external_scope=external_scope,
            adapter=adapter,
        )

    def get(self, source_system: str, external_scope: str) -> CalendarAdapterBinding | None:
        return self._bindings.get(
            (
                _required_text(source_system, "source_system").lower(),
                _required_text(external_scope, "external_scope"),
            )
        )

    def list_bindings(self) -> tuple[CalendarAdapterBinding, ...]:
        return tuple(self._bindings[key] for key in sorted(self._bindings))


class CalendarSyncCoordinator:
    """Fetch and reconcile bounded calendar windows with auditable provider failures."""

    def __init__(
        self,
        session: Session,
        registry: CalendarAdapterRegistry,
        *,
        max_window_days: int = 31,
    ) -> None:
        if isinstance(max_window_days, bool) or not 1 <= max_window_days <= 366:
            raise CalendarOperationError("max_window_days must be between 1 and 366")
        self.session = session
        self.registry = registry
        self.max_window_days = max_window_days
        self.state = IntegrationStateStore(session)

    def synchronize(
        self,
        *,
        source_system: str,
        external_scope: str,
        starts_at: datetime,
        ends_at: datetime,
        synced_at: datetime | None = None,
    ) -> CalendarReconciliationResult:
        source_system = _required_text(source_system, "source_system").lower()
        external_scope = _required_text(external_scope, "external_scope")
        try:
            window = CalendarWindow(starts_at=starts_at, ends_at=ends_at)
        except IntegrationContractError as exc:
            raise CalendarOperationError(str(exc)) from exc
        if window.ends_at - window.starts_at > timedelta(days=self.max_window_days):
            raise CalendarOperationError(
                f"Calendar synchronization window cannot exceed {self.max_window_days} days"
            )
        binding = self.registry.get(source_system, external_scope)
        if binding is None:
            raise CalendarOperationError("Calendar adapter is not available for this connection")
        require_read_only_capabilities(binding.adapter.capabilities)
        operation_time = _as_utc(synced_at or utc_now(), "synced_at")
        try:
            events = binding.adapter.list_events(window)
        except Exception as exc:
            run = self.state.start_run(
                source_system=source_system,
                resource_kind="calendar",
                external_scope=external_scope,
                window_starts_at=window.starts_at,
                window_ends_at=window.ends_at,
                started_at=operation_time,
            )
            message = str(exc).strip() or type(exc).__name__
            self.state.record_error(
                run.id,
                code="calendar_provider_error",
                message=message,
                occurred_at=operation_time,
            )
            self.state.finish_run(
                run.id,
                seen_count=0,
                status="failed",
                completed_at=operation_time,
            )
            raise CalendarOperationError(
                "Calendar provider request failed; inspect the recorded run",
                run_id=run.id,
            ) from None

        return CalendarReconciler(self.session).reconcile(
            events,
            window=window,
            source_system=source_system,
            external_scope=external_scope,
            synced_at=operation_time,
            capabilities=binding.adapter.capabilities,
        )

    def retry(
        self, run_id: str, *, synced_at: datetime | None = None
    ) -> CalendarReconciliationResult:
        run = self.session.get(SyncRun, _required_text(run_id, "run_id"))
        if run is None:
            raise CalendarOperationError(f"Synchronization run not found: {run_id}")
        if run.resource_kind != "calendar":
            raise CalendarOperationError("Only calendar synchronization runs can be retried")
        if run.status not in {"failed", "partial"}:
            raise CalendarOperationError("Only failed or partial runs can be retried")
        if not run.external_scope or not run.window_starts_at or not run.window_ends_at:
            raise CalendarOperationError("Synchronization run no longer has retry context")
        return self.synchronize(
            source_system=run.source_system,
            external_scope=run.external_scope,
            starts_at=_stored_as_utc(run.window_starts_at),
            ends_at=_stored_as_utc(run.window_ends_at),
            synced_at=synced_at,
        )


def _required_text(value: str, field_name: str) -> str:
    normalized = value.strip()
    if not normalized:
        raise CalendarOperationError(f"{field_name} cannot be empty")
    return normalized


def _as_utc(value: datetime, field_name: str) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise CalendarOperationError(f"{field_name} must include a timezone")
    return value.astimezone(UTC)


def _stored_as_utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)
