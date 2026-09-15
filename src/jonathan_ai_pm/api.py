from datetime import date, datetime
from hmac import compare_digest
from typing import Annotated, Any

from fastapi import Depends, FastAPI, HTTPException, Query, Request, Response, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from jonathan_ai_pm import __version__
from jonathan_ai_pm.audit import list_audit_events
from jonathan_ai_pm.config import Settings, get_settings
from jonathan_ai_pm.db import get_session
from jonathan_ai_pm.integrations import (
    CalendarAdapterRegistry,
    CalendarAssociationError,
    CalendarAssociationService,
    CalendarOperationError,
    CalendarSyncCoordinator,
    IntegrationSecurityError,
    IntegrationStateError,
    IntegrationStateStore,
    normalize_permissions,
    require_read_only_capabilities,
)
from jonathan_ai_pm.models import CalendarImportReview, SyncRun
from jonathan_ai_pm.portability import export_snapshot, import_snapshot
from jonathan_ai_pm.schemas import (
    ActionItemCreate,
    ActionItemRead,
    ActionItemStatus,
    ActionItemToTask,
    ActionItemUpdate,
    AuditEventRead,
    CalendarImportReviewRead,
    CalendarReviewConfirm,
    CalendarSyncRequest,
    CalendarSyncResult,
    CaptureCreate,
    CaptureDisposition,
    CaptureRead,
    CaptureStatus,
    CaptureTriage,
    ClientCreate,
    ClientRead,
    ClientUpdate,
    DeliverableCreate,
    DeliverableRead,
    DeliverableStatus,
    DeliverableUpdate,
    EntityId,
    EntityKind,
    EveningClose,
    IntegrationConnectionRead,
    IntegrationStatusRead,
    MeetingCreate,
    MeetingPreparation,
    MeetingRead,
    MeetingReviewCreate,
    MeetingReviewQueue,
    MeetingReviewResult,
    MeetingStatus,
    MeetingUpdate,
    MorningBrief,
    ProgressSummary,
    ProjectCreate,
    ProjectHealth,
    ProjectRead,
    ProjectStatus,
    ProjectUpdate,
    RecordStatus,
    SnapshotDocument,
    SnapshotImportResult,
    SyncRunErrorRead,
    SyncRunRead,
    SyncRunStatus,
    TaskComplete,
    TaskCreate,
    TaskPriority,
    TaskRead,
    TaskStatus,
    TaskUpdate,
    TranslatableEntityKind,
    TranslationCreate,
    TranslationField,
    TranslationRead,
    TranslationUpdate,
    WorkLogCreate,
    WorkLogRead,
    WorkspaceCreate,
    WorkspaceRead,
    WorkspaceUpdate,
)
from jonathan_ai_pm.security import install_log_redaction
from jonathan_ai_pm.services import DomainRuleError, DomainStore

install_log_redaction()
app = FastAPI(title="Jonathan AI PM", version=__version__)
RawDbSession = Annotated[Session, Depends(get_session)]
calendar_adapter_registry = CalendarAdapterRegistry()


def get_integration_settings() -> Settings:
    return get_settings()


def get_calendar_adapter_registry() -> CalendarAdapterRegistry:
    return calendar_adapter_registry


IntegrationSettings = Annotated[Settings, Depends(get_integration_settings)]
CalendarRegistry = Annotated[CalendarAdapterRegistry, Depends(get_calendar_adapter_registry)]


def authorize_integration_operations(
    request: Request,
    settings: IntegrationSettings,
) -> None:
    if not settings.integration_operations_enabled:
        raise HTTPException(status_code=503, detail="Integration operations are disabled")
    expected = (
        settings.integration_operation_key.get_secret_value()
        if settings.integration_operation_key
        else ""
    )
    supplied = request.headers.get("X-Integration-Key", "")
    if not expected or not compare_digest(supplied, expected):
        raise HTTPException(status_code=401, detail="Invalid integration operation key")


IntegrationAccess = Annotated[None, Depends(authorize_integration_operations)]


def request_session(request: Request, session: RawDbSession) -> Session:
    actor = (request.headers.get("X-Actor") or "local-user").strip()
    session.info["actor"] = actor[:200] or "local-user"
    return session


DbSession = Annotated[Session, Depends(request_session)]


@app.get("/health", tags=["system"])
def health() -> dict[str, str]:
    return {"status": "ok", "version": __version__}


@app.get("/api/v1/briefs/morning", response_model=MorningBrief, tags=["briefs"])
def morning_brief(
    session: DbSession,
    brief_date: Annotated[date | None, Query(alias="date")] = None,
    due_soon_days: Annotated[int, Query(ge=0, le=30)] = 3,
):
    try:
        return _store(session).morning_brief(
            get_settings().app_timezone,
            brief_date=brief_date,
            due_soon_days=due_soon_days,
        )
    except DomainRuleError as exc:
        raise _domain_http_error(exc) from exc


@app.get("/api/v1/briefs/evening", response_model=EveningClose, tags=["briefs"])
def evening_close(
    session: DbSession,
    close_date: Annotated[date | None, Query(alias="date")] = None,
):
    try:
        return _store(session).evening_close(
            get_settings().app_timezone,
            close_date=close_date,
        )
    except DomainRuleError as exc:
        raise _domain_http_error(exc) from exc


@app.get(
    "/api/v1/briefs/meetings",
    response_model=MeetingPreparation,
    tags=["briefs"],
)
def meeting_preparation(
    session: DbSession,
    preparation_date: Annotated[date | None, Query(alias="date")] = None,
    due_soon_days: Annotated[int, Query(ge=0, le=30)] = 7,
):
    try:
        return _store(session).meeting_preparation(
            get_settings().app_timezone,
            preparation_date=preparation_date,
            due_soon_days=due_soon_days,
        )
    except DomainRuleError as exc:
        raise _domain_http_error(exc) from exc


@app.get(
    "/api/v1/briefs/meeting-reviews",
    response_model=MeetingReviewQueue,
    tags=["briefs"],
)
def meeting_review_queue(
    session: DbSession,
    review_through: Annotated[date | None, Query(alias="date")] = None,
):
    try:
        return _store(session).meeting_review_queue(
            get_settings().app_timezone,
            review_through=review_through,
        )
    except DomainRuleError as exc:
        raise _domain_http_error(exc) from exc


@app.get("/api/v1/reports/progress", response_model=ProgressSummary, tags=["reports"])
def progress_summary(
    session: DbSession,
    as_of: date | None = None,
    work_from: date | None = None,
    work_to: date | None = None,
):
    try:
        return _store(session).progress_summary(
            get_settings().app_timezone,
            as_of=as_of,
            work_from=work_from,
            work_to=work_to,
        )
    except DomainRuleError as exc:
        raise _domain_http_error(exc) from exc


@app.get("/api/v1/audit-events", response_model=list[AuditEventRead], tags=["audit"])
def get_audit_events(
    session: DbSession,
    entity_kind: EntityKind | None = None,
    entity_id: EntityId | None = None,
    actor: Annotated[str | None, Query(max_length=200)] = None,
):
    return list_audit_events(
        session,
        entity_kind=entity_kind,
        entity_id=entity_id,
        actor=actor,
    )


@app.get(
    "/api/v1/integrations/status",
    response_model=IntegrationStatusRead,
    tags=["integrations"],
)
def integration_status(
    _access: IntegrationAccess,
    session: DbSession,
    settings: IntegrationSettings,
    registry: CalendarRegistry,
):
    configured = {
        ("microsoft-365", scope)
        for scope in _configured_calendar_scopes(settings.microsoft_calendar_ids)
    }
    configured.update(
        (binding.source_system, binding.external_scope) for binding in registry.list_bindings()
    )
    state = IntegrationStateStore(session)
    connections: list[IntegrationConnectionRead] = []
    for source_system, external_scope in sorted(configured):
        binding = registry.get(source_system, external_scope)
        read_only = False
        if binding is not None:
            try:
                require_read_only_capabilities(binding.adapter.capabilities)
                read_only = True
            except IntegrationSecurityError:
                pass
        enabled = (
            settings.microsoft_calendar_enabled
            if source_system == "microsoft-365"
            else binding is not None
        )
        permissions = (
            list(normalize_permissions(settings.microsoft_graph_scopes))
            if source_system == "microsoft-365"
            else []
        )
        recent_runs = state.list_runs(
            source_system=source_system,
            external_scope=external_scope,
            limit=1,
        )
        connections.append(
            IntegrationConnectionRead(
                source_system=source_system,
                external_scope=external_scope,
                enabled=enabled,
                adapter_available=binding is not None,
                read_only=read_only,
                ready=(
                    settings.integration_operations_enabled
                    and enabled
                    and binding is not None
                    and read_only
                ),
                permissions=permissions,
                last_run=_sync_run_read(recent_runs[0]) if recent_runs else None,
            )
        )
    return IntegrationStatusRead(
        operations_enabled=settings.integration_operations_enabled,
        max_sync_window_days=settings.integration_max_sync_window_days,
        connections=connections,
    )


@app.post(
    "/api/v1/integrations/calendar/sync",
    response_model=CalendarSyncResult,
    tags=["integrations"],
)
def synchronize_calendar(
    payload: CalendarSyncRequest,
    _access: IntegrationAccess,
    session: DbSession,
    settings: IntegrationSettings,
    registry: CalendarRegistry,
):
    _require_connection_enabled(payload.source_system, settings)
    coordinator = CalendarSyncCoordinator(
        session,
        registry,
        max_window_days=settings.integration_max_sync_window_days,
    )
    try:
        result = coordinator.synchronize(**payload.model_dump())
    except (CalendarOperationError, IntegrationSecurityError) as exc:
        session.rollback()
        raise _calendar_operation_http_error(exc) from exc
    return _sync_result(result)


@app.get(
    "/api/v1/integrations/sync-runs",
    response_model=list[SyncRunRead],
    tags=["integrations"],
)
def list_sync_runs(
    _access: IntegrationAccess,
    session: DbSession,
    source_system: Annotated[str | None, Query(max_length=80)] = None,
    external_scope: Annotated[str | None, Query(max_length=240)] = None,
    run_status: Annotated[SyncRunStatus | None, Query(alias="status")] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
):
    try:
        runs = IntegrationStateStore(session).list_runs(
            source_system=source_system,
            external_scope=external_scope,
            status=run_status,
            limit=limit,
        )
    except IntegrationStateError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return [_sync_run_read(run) for run in runs]


@app.get(
    "/api/v1/integrations/sync-runs/{run_id}",
    response_model=SyncRunRead,
    tags=["integrations"],
)
def get_sync_run(run_id: EntityId, _access: IntegrationAccess, session: DbSession):
    run = IntegrationStateStore(session).get_run(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Synchronization run not found")
    return _sync_run_read(run)


@app.get(
    "/api/v1/integrations/sync-runs/{run_id}/errors",
    response_model=list[SyncRunErrorRead],
    tags=["integrations"],
)
def list_sync_run_errors(
    run_id: EntityId,
    _access: IntegrationAccess,
    session: DbSession,
):
    try:
        return IntegrationStateStore(session).list_errors(run_id)
    except IntegrationStateError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post(
    "/api/v1/integrations/sync-runs/{run_id}/retry",
    response_model=CalendarSyncResult,
    tags=["integrations"],
)
def retry_sync_run(
    run_id: EntityId,
    _access: IntegrationAccess,
    session: DbSession,
    settings: IntegrationSettings,
    registry: CalendarRegistry,
):
    original = IntegrationStateStore(session).get_run(run_id)
    if original is None:
        raise HTTPException(status_code=404, detail="Synchronization run not found")
    _require_connection_enabled(original.source_system, settings)
    coordinator = CalendarSyncCoordinator(
        session,
        registry,
        max_window_days=settings.integration_max_sync_window_days,
    )
    try:
        result = coordinator.retry(run_id)
    except (CalendarOperationError, IntegrationSecurityError) as exc:
        session.rollback()
        raise _calendar_operation_http_error(exc) from exc
    return _sync_result(result, retry_of_run_id=run_id)


@app.get(
    "/api/v1/integrations/calendar/reviews",
    response_model=list[CalendarImportReviewRead],
    tags=["integrations"],
)
def list_calendar_reviews(
    _access: IntegrationAccess,
    session: DbSession,
    source_system: Annotated[str | None, Query(max_length=80)] = None,
    external_scope: Annotated[str | None, Query(max_length=240)] = None,
):
    try:
        return CalendarAssociationService(session).list_pending(
            source_system=source_system,
            external_scope=external_scope,
        )
    except CalendarAssociationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.post(
    "/api/v1/integrations/calendar/reviews/{review_id}/confirm",
    response_model=CalendarImportReviewRead,
    tags=["integrations"],
)
def confirm_calendar_review(
    review_id: EntityId,
    payload: CalendarReviewConfirm,
    _access: IntegrationAccess,
    session: DbSession,
):
    try:
        CalendarAssociationService(session).confirm(
            review_id,
            project_id=payload.project_id,
            actor=str(session.info.get("actor", "local-user")),
        )
    except CalendarAssociationError as exc:
        session.rollback()
        raise _calendar_association_http_error(exc) from exc
    return session.get(CalendarImportReview, review_id)


@app.post(
    "/api/v1/integrations/calendar/reviews/{review_id}/dismiss",
    response_model=CalendarImportReviewRead,
    tags=["integrations"],
)
def dismiss_calendar_review(
    review_id: EntityId,
    _access: IntegrationAccess,
    session: DbSession,
):
    try:
        return CalendarAssociationService(session).dismiss(
            review_id,
            actor=str(session.info.get("actor", "local-user")),
        )
    except CalendarAssociationError as exc:
        session.rollback()
        raise _calendar_association_http_error(exc) from exc


@app.get("/api/v1/snapshots/export", response_model=SnapshotDocument, tags=["snapshots"])
def export_portable_snapshot(session: DbSession):
    return export_snapshot(session)


@app.post(
    "/api/v1/snapshots/import",
    response_model=SnapshotImportResult,
    status_code=201,
    tags=["snapshots"],
)
def import_portable_snapshot(payload: SnapshotDocument, session: DbSession):
    try:
        return import_snapshot(session, payload)
    except DomainRuleError as exc:
        session.rollback()
        raise _domain_http_error(exc) from exc
    except IntegrityError as exc:
        session.rollback()
        raise HTTPException(status_code=409, detail="Snapshot relationship conflict") from exc


def _configured_calendar_scopes(value: str) -> tuple[str, ...]:
    return tuple(dict.fromkeys(scope.strip() for scope in value.split(",") if scope.strip()))


def _require_connection_enabled(source_system: str, settings: Settings) -> None:
    if source_system.strip().lower() == "microsoft-365" and not settings.microsoft_calendar_enabled:
        raise HTTPException(status_code=409, detail="Microsoft 365 calendar is disabled")


def _sync_run_read(run: SyncRun) -> SyncRunRead:
    retryable = (
        run.resource_kind == "calendar"
        and run.status in {"failed", "partial"}
        and bool(run.external_scope and run.window_starts_at and run.window_ends_at)
    )
    return SyncRunRead.model_validate(
        {
            **{column.name: getattr(run, column.name) for column in SyncRun.__table__.columns},
            "retryable": retryable,
        }
    )


def _sync_result(result, *, retry_of_run_id: str | None = None) -> CalendarSyncResult:
    return CalendarSyncResult(
        run_id=result.run_id,
        status=result.status,
        seen_count=result.seen_count,
        created_count=result.created_count,
        updated_count=result.updated_count,
        unchanged_count=result.unchanged_count,
        skipped_count=result.skipped_count,
        error_count=result.error_count,
        missing_identity_ids=list(result.missing_identity_ids),
        queued_review_ids=list(result.queued_review_ids),
        retry_of_run_id=retry_of_run_id,
    )


def _calendar_operation_http_error(
    exc: CalendarOperationError | IntegrationSecurityError,
) -> HTTPException:
    if isinstance(exc, CalendarOperationError) and exc.run_id:
        return HTTPException(
            status_code=502,
            detail={"message": str(exc), "run_id": exc.run_id},
        )
    message = str(exc)
    code = 404 if "not found" in message.lower() else 409
    return HTTPException(status_code=code, detail=message)


def _calendar_association_http_error(exc: CalendarAssociationError) -> HTTPException:
    code = 404 if "not found" in str(exc).lower() else 422
    return HTTPException(status_code=code, detail=str(exc))


def _store(session: Session) -> DomainStore:
    return DomainStore(session)


def _create(session: Session, kind: str, payload) -> Any:
    try:
        return _store(session).create(kind, **payload.model_dump())
    except DomainRuleError as exc:
        session.rollback()
        raise _domain_http_error(exc) from exc
    except IntegrityError as exc:
        session.rollback()
        raise HTTPException(status_code=409, detail="Record or relationship conflict") from exc


def _get(session: Session, kind: str, entity_id: str) -> Any:
    entity = _store(session).get(kind, entity_id)
    if entity is None:
        raise HTTPException(status_code=404, detail=f"{kind} not found")
    return entity


def _update(session: Session, kind: str, entity_id: str, payload) -> Any:
    try:
        return _store(session).update(kind, entity_id, **payload.model_dump(exclude_unset=True))
    except DomainRuleError as exc:
        session.rollback()
        raise _domain_http_error(exc) from exc
    except IntegrityError as exc:
        session.rollback()
        raise HTTPException(status_code=409, detail="Record or relationship conflict") from exc


def _delete(session: Session, kind: str, entity_id: str) -> Response:
    try:
        _store(session).delete(kind, entity_id)
    except DomainRuleError as exc:
        raise _domain_http_error(exc) from exc
    except IntegrityError as exc:
        session.rollback()
        raise HTTPException(status_code=409, detail="Record is still referenced") from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)


def _domain_http_error(exc: DomainRuleError) -> HTTPException:
    code = 404 if " not found:" in str(exc) else 422
    return HTTPException(status_code=code, detail=str(exc))


@app.post("/api/v1/workspaces", response_model=WorkspaceRead, status_code=201, tags=["workspaces"])
def create_workspace(payload: WorkspaceCreate, session: DbSession):
    return _create(session, "workspace", payload)


@app.get("/api/v1/workspaces", response_model=list[WorkspaceRead], tags=["workspaces"])
def list_workspaces(
    session: DbSession,
    record_status: Annotated[RecordStatus | None, Query(alias="status")] = None,
):
    return _store(session).list("workspace", status=record_status)


@app.get("/api/v1/workspaces/{entity_id}", response_model=WorkspaceRead, tags=["workspaces"])
def get_workspace(entity_id: str, session: DbSession):
    return _get(session, "workspace", entity_id)


@app.patch("/api/v1/workspaces/{entity_id}", response_model=WorkspaceRead, tags=["workspaces"])
def update_workspace(entity_id: str, payload: WorkspaceUpdate, session: DbSession):
    return _update(session, "workspace", entity_id, payload)


@app.delete("/api/v1/workspaces/{entity_id}", status_code=204, tags=["workspaces"])
def delete_workspace(entity_id: str, session: DbSession):
    return _delete(session, "workspace", entity_id)


@app.post("/api/v1/clients", response_model=ClientRead, status_code=201, tags=["clients"])
def create_client(payload: ClientCreate, session: DbSession):
    return _create(session, "client", payload)


@app.get("/api/v1/clients", response_model=list[ClientRead], tags=["clients"])
def list_clients(
    session: DbSession,
    workspace_id: EntityId | None = None,
    record_status: Annotated[RecordStatus | None, Query(alias="status")] = None,
):
    return _store(session).list("client", workspace_id=workspace_id, status=record_status)


@app.get("/api/v1/clients/{entity_id}", response_model=ClientRead, tags=["clients"])
def get_client(entity_id: str, session: DbSession):
    return _get(session, "client", entity_id)


@app.patch("/api/v1/clients/{entity_id}", response_model=ClientRead, tags=["clients"])
def update_client(entity_id: str, payload: ClientUpdate, session: DbSession):
    return _update(session, "client", entity_id, payload)


@app.delete("/api/v1/clients/{entity_id}", status_code=204, tags=["clients"])
def delete_client(entity_id: str, session: DbSession):
    return _delete(session, "client", entity_id)


@app.post("/api/v1/projects", response_model=ProjectRead, status_code=201, tags=["projects"])
def create_project(payload: ProjectCreate, session: DbSession):
    return _create(session, "project", payload)


@app.get("/api/v1/projects", response_model=list[ProjectRead], tags=["projects"])
def list_projects(
    session: DbSession,
    client_id: EntityId | None = None,
    project_status: Annotated[ProjectStatus | None, Query(alias="status")] = None,
    health: ProjectHealth | None = None,
):
    return _store(session).list(
        "project", client_id=client_id, status=project_status, health=health
    )


@app.get("/api/v1/projects/{entity_id}", response_model=ProjectRead, tags=["projects"])
def get_project(entity_id: str, session: DbSession):
    return _get(session, "project", entity_id)


@app.patch("/api/v1/projects/{entity_id}", response_model=ProjectRead, tags=["projects"])
def update_project(entity_id: str, payload: ProjectUpdate, session: DbSession):
    return _update(session, "project", entity_id, payload)


@app.delete("/api/v1/projects/{entity_id}", status_code=204, tags=["projects"])
def delete_project(entity_id: str, session: DbSession):
    return _delete(session, "project", entity_id)


@app.post(
    "/api/v1/deliverables",
    response_model=DeliverableRead,
    status_code=201,
    tags=["deliverables"],
)
def create_deliverable(payload: DeliverableCreate, session: DbSession):
    if payload.status == "in_review":
        raise HTTPException(status_code=422, detail="Use the review transition endpoint")
    return _create(session, "deliverable", payload)


@app.get("/api/v1/deliverables", response_model=list[DeliverableRead], tags=["deliverables"])
def list_deliverables(
    session: DbSession,
    project_id: EntityId | None = None,
    deliverable_status: Annotated[DeliverableStatus | None, Query(alias="status")] = None,
    due_from: date | None = None,
    due_to: date | None = None,
):
    return _store(session).list(
        "deliverable",
        project_id=project_id,
        status=deliverable_status,
        due_at_from=due_from,
        due_at_to=due_to,
    )


@app.get(
    "/api/v1/deliverables/{entity_id}",
    response_model=DeliverableRead,
    tags=["deliverables"],
)
def get_deliverable(entity_id: str, session: DbSession):
    return _get(session, "deliverable", entity_id)


@app.patch(
    "/api/v1/deliverables/{entity_id}",
    response_model=DeliverableRead,
    tags=["deliverables"],
)
def update_deliverable(entity_id: str, payload: DeliverableUpdate, session: DbSession):
    if payload.status == "in_review":
        raise HTTPException(status_code=422, detail="Use the review transition endpoint")
    return _update(session, "deliverable", entity_id, payload)


@app.post(
    "/api/v1/deliverables/{entity_id}/review",
    response_model=DeliverableRead,
    tags=["deliverables"],
)
def review_deliverable(entity_id: str, session: DbSession):
    try:
        return _store(session).move_deliverable_to_review(entity_id)
    except DomainRuleError as exc:
        session.rollback()
        raise _domain_http_error(exc) from exc


@app.delete("/api/v1/deliverables/{entity_id}", status_code=204, tags=["deliverables"])
def delete_deliverable(entity_id: str, session: DbSession):
    return _delete(session, "deliverable", entity_id)


@app.post("/api/v1/tasks", response_model=TaskRead, status_code=201, tags=["tasks"])
def create_task(payload: TaskCreate, session: DbSession):
    if payload.status == "done":
        raise HTTPException(status_code=422, detail="Use the task completion endpoint")
    return _create(session, "task", payload)


@app.get("/api/v1/tasks", response_model=list[TaskRead], tags=["tasks"])
def list_tasks(
    session: DbSession,
    project_id: EntityId | None = None,
    deliverable_id: EntityId | None = None,
    task_status: Annotated[TaskStatus | None, Query(alias="status")] = None,
    priority: TaskPriority | None = None,
    due_from: date | None = None,
    due_to: date | None = None,
):
    return _store(session).list(
        "task",
        project_id=project_id,
        deliverable_id=deliverable_id,
        status=task_status,
        priority=priority,
        due_at_from=due_from,
        due_at_to=due_to,
    )


@app.get("/api/v1/tasks/{entity_id}", response_model=TaskRead, tags=["tasks"])
def get_task(entity_id: str, session: DbSession):
    return _get(session, "task", entity_id)


@app.patch("/api/v1/tasks/{entity_id}", response_model=TaskRead, tags=["tasks"])
def update_task(entity_id: str, payload: TaskUpdate, session: DbSession):
    if payload.status == "done":
        raise HTTPException(status_code=422, detail="Use the task completion endpoint")
    if payload.status == "in_progress":
        raise HTTPException(status_code=422, detail="Use the task start endpoint")
    return _update(session, "task", entity_id, payload)


@app.post("/api/v1/tasks/{entity_id}/start", response_model=TaskRead, tags=["tasks"])
def start_task(entity_id: str, session: DbSession):
    try:
        return _store(session).start_task(entity_id)
    except DomainRuleError as exc:
        session.rollback()
        raise _domain_http_error(exc) from exc


@app.post(
    "/api/v1/tasks/{entity_id}/work-logs",
    response_model=WorkLogRead,
    status_code=201,
    tags=["tasks"],
)
def add_task_work_log(entity_id: str, payload: WorkLogCreate, session: DbSession):
    try:
        return _store(session).add_work_log(
            entity_id,
            minutes=payload.minutes,
            summary=payload.summary,
            started_at=payload.started_at,
        )
    except DomainRuleError as exc:
        session.rollback()
        raise _domain_http_error(exc) from exc
    except IntegrityError as exc:
        session.rollback()
        raise HTTPException(status_code=409, detail="Work-log conflict") from exc


@app.get(
    "/api/v1/tasks/{entity_id}/work-logs",
    response_model=list[WorkLogRead],
    tags=["tasks"],
)
def list_task_work_logs(entity_id: str, session: DbSession):
    try:
        return _store(session).list_task_work_logs(entity_id)
    except DomainRuleError as exc:
        raise _domain_http_error(exc) from exc


@app.post("/api/v1/tasks/{entity_id}/complete", response_model=TaskRead, tags=["tasks"])
def complete_task(entity_id: str, payload: TaskComplete, session: DbSession):
    try:
        return _store(session).complete_task(entity_id, payload.completion_note)
    except DomainRuleError as exc:
        session.rollback()
        raise _domain_http_error(exc) from exc


@app.delete("/api/v1/tasks/{entity_id}", status_code=204, tags=["tasks"])
def delete_task(entity_id: str, session: DbSession):
    return _delete(session, "task", entity_id)


@app.post("/api/v1/meetings", response_model=MeetingRead, status_code=201, tags=["meetings"])
def create_meeting(payload: MeetingCreate, session: DbSession):
    return _create(session, "meeting", payload)


@app.get("/api/v1/meetings", response_model=list[MeetingRead], tags=["meetings"])
def list_meetings(
    session: DbSession,
    project_id: EntityId | None = None,
    meeting_status: Annotated[MeetingStatus | None, Query(alias="status")] = None,
    starts_from: datetime | None = None,
    starts_to: datetime | None = None,
):
    return _store(session).list(
        "meeting",
        project_id=project_id,
        status=meeting_status,
        starts_at_from=starts_from,
        starts_at_to=starts_to,
    )


@app.get("/api/v1/meetings/{entity_id}", response_model=MeetingRead, tags=["meetings"])
def get_meeting(entity_id: str, session: DbSession):
    return _get(session, "meeting", entity_id)


@app.patch("/api/v1/meetings/{entity_id}", response_model=MeetingRead, tags=["meetings"])
def update_meeting(entity_id: str, payload: MeetingUpdate, session: DbSession):
    return _update(session, "meeting", entity_id, payload)


@app.post(
    "/api/v1/meetings/{entity_id}/review",
    response_model=MeetingReviewResult,
    tags=["meetings"],
)
def review_meeting(entity_id: str, payload: MeetingReviewCreate, session: DbSession):
    try:
        return _store(session).review_meeting(
            entity_id,
            decision=payload.decision,
            summary=payload.summary,
            actions=[action.model_dump() for action in payload.actions],
        )
    except DomainRuleError as exc:
        session.rollback()
        raise _domain_http_error(exc) from exc
    except IntegrityError as exc:
        session.rollback()
        raise HTTPException(status_code=409, detail="Meeting review conflict") from exc


@app.delete("/api/v1/meetings/{entity_id}", status_code=204, tags=["meetings"])
def delete_meeting(entity_id: str, session: DbSession):
    return _delete(session, "meeting", entity_id)


@app.post(
    "/api/v1/action-items",
    response_model=ActionItemRead,
    status_code=201,
    tags=["action-items"],
)
def create_action_item(payload: ActionItemCreate, session: DbSession):
    return _create(session, "action_item", payload)


@app.get("/api/v1/action-items", response_model=list[ActionItemRead], tags=["action-items"])
def list_action_items(
    session: DbSession,
    meeting_id: EntityId | None = None,
    item_status: Annotated[ActionItemStatus | None, Query(alias="status")] = None,
):
    return _store(session).list("action_item", meeting_id=meeting_id, status=item_status)


@app.get(
    "/api/v1/action-items/{entity_id}",
    response_model=ActionItemRead,
    tags=["action-items"],
)
def get_action_item(entity_id: str, session: DbSession):
    return _get(session, "action_item", entity_id)


@app.patch(
    "/api/v1/action-items/{entity_id}",
    response_model=ActionItemRead,
    tags=["action-items"],
)
def update_action_item(entity_id: str, payload: ActionItemUpdate, session: DbSession):
    return _update(session, "action_item", entity_id, payload)


@app.post(
    "/api/v1/action-items/{entity_id}/task",
    response_model=TaskRead,
    status_code=201,
    tags=["action-items"],
)
def action_item_to_task(entity_id: str, payload: ActionItemToTask, session: DbSession):
    try:
        return _store(session).create_task_from_action(
            entity_id,
            payload.task_id,
            payload.priority,
            payload.due_at,
            payload.deliverable_id,
        )
    except DomainRuleError as exc:
        session.rollback()
        raise _domain_http_error(exc) from exc
    except IntegrityError as exc:
        session.rollback()
        raise HTTPException(status_code=409, detail="Record or relationship conflict") from exc


@app.delete("/api/v1/action-items/{entity_id}", status_code=204, tags=["action-items"])
def delete_action_item(entity_id: str, session: DbSession):
    return _delete(session, "action_item", entity_id)


@app.post("/api/v1/captures", response_model=CaptureRead, status_code=201, tags=["captures"])
def create_capture(payload: CaptureCreate, session: DbSession):
    try:
        return _store(session).capture(payload.text)
    except IntegrityError as exc:
        session.rollback()
        raise HTTPException(status_code=409, detail="Capture conflict") from exc


@app.get("/api/v1/captures", response_model=list[CaptureRead], tags=["captures"])
def list_captures(
    session: DbSession,
    capture_status: CaptureStatus | None = None,
    disposition: CaptureDisposition | None = None,
    project_id: EntityId | None = None,
):
    return _store(session).list(
        "capture", status=capture_status, disposition=disposition, project_id=project_id
    )


@app.get("/api/v1/captures/{entity_id}", response_model=CaptureRead, tags=["captures"])
def get_capture(entity_id: EntityId, session: DbSession):
    return _get(session, "capture", entity_id)


@app.post("/api/v1/captures/{entity_id}/triage", response_model=CaptureRead, tags=["captures"])
def triage_capture(entity_id: EntityId, payload: CaptureTriage, session: DbSession):
    try:
        return _store(session).triage_capture(
            entity_id,
            payload.disposition,
            project_id=payload.project_id,
            task_id=payload.task_id,
            action_item_id=payload.action_item_id,
            meeting_id=payload.meeting_id,
            deliverable_id=payload.deliverable_id,
            owner=payload.owner,
            priority=payload.priority,
            due_at=payload.due_at,
            note=payload.note,
        )
    except DomainRuleError as exc:
        session.rollback()
        raise _domain_http_error(exc) from exc
    except IntegrityError as exc:
        session.rollback()
        raise HTTPException(status_code=409, detail="Record or relationship conflict") from exc


@app.post(
    "/api/v1/translations",
    response_model=TranslationRead,
    status_code=201,
    tags=["translations"],
)
def create_translation(payload: TranslationCreate, session: DbSession):
    return _create(session, "translation", payload)


@app.get("/api/v1/translations", response_model=list[TranslationRead], tags=["translations"])
def list_translations(
    session: DbSession,
    entity_kind: TranslatableEntityKind | None = None,
    entity_id: EntityId | None = None,
    field_name: TranslationField | None = None,
    language: str | None = None,
):
    return _store(session).list(
        "translation",
        entity_kind=entity_kind,
        entity_id=entity_id,
        field_name=field_name,
        language=language,
    )


@app.get(
    "/api/v1/translations/{entity_id}",
    response_model=TranslationRead,
    tags=["translations"],
)
def get_translation(entity_id: EntityId, session: DbSession):
    return _get(session, "translation", entity_id)


@app.patch(
    "/api/v1/translations/{entity_id}",
    response_model=TranslationRead,
    tags=["translations"],
)
def update_translation(
    entity_id: EntityId,
    payload: TranslationUpdate,
    session: DbSession,
):
    return _update(session, "translation", entity_id, payload)


@app.delete("/api/v1/translations/{entity_id}", status_code=204, tags=["translations"])
def delete_translation(entity_id: EntityId, session: DbSession):
    return _delete(session, "translation", entity_id)
