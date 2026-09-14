from datetime import date, datetime
from typing import Annotated, Any

from fastapi import Depends, FastAPI, HTTPException, Query, Request, Response, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from jonathan_ai_pm import __version__
from jonathan_ai_pm.audit import list_audit_events
from jonathan_ai_pm.config import get_settings
from jonathan_ai_pm.db import get_session
from jonathan_ai_pm.portability import export_snapshot, import_snapshot
from jonathan_ai_pm.schemas import (
    ActionItemCreate,
    ActionItemRead,
    ActionItemStatus,
    ActionItemToTask,
    ActionItemUpdate,
    AuditEventRead,
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
    MeetingCreate,
    MeetingRead,
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
    TaskComplete,
    TaskCreate,
    TaskPriority,
    TaskRead,
    TaskStatus,
    TaskUpdate,
    WorkLogCreate,
    WorkLogRead,
    WorkspaceCreate,
    WorkspaceRead,
    WorkspaceUpdate,
)
from jonathan_ai_pm.services import DomainRuleError, DomainStore

app = FastAPI(title="Jonathan AI PM", version=__version__)
RawDbSession = Annotated[Session, Depends(get_session)]


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
