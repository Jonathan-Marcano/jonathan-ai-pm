from datetime import date
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, Request, Response
from sqlalchemy.exc import IntegrityError

from faroflow.schemas import (
    EntityId,
    TaskComplete,
    TaskCreate,
    TaskPriority,
    TaskRead,
    TaskStatus,
    TaskUpdate,
    WorkLogCreate,
    WorkLogRead,
)
from faroflow.services import DomainRuleError

from .deps import (
    DbSession,
    PageLimit,
    PageOffset,
    create_record,
    delete_record,
    domain_http_error,
    get_record,
    page_items,
    set_page_links,
    store,
    update_record,
)

router = APIRouter()


@router.post("/api/v1/tasks", response_model=TaskRead, status_code=201, tags=["tasks"])
def create_task(payload: TaskCreate, session: DbSession):
    if payload.status == "done":
        raise HTTPException(status_code=422, detail="Use the task completion endpoint")
    return create_record(session, "task", payload)


@router.get("/api/v1/tasks", response_model=list[TaskRead], tags=["tasks"])
def list_tasks(
    session: DbSession,
    response: Response,
    request: Request,
    project_id: EntityId | None = None,
    deliverable_id: EntityId | None = None,
    task_status: Annotated[TaskStatus | None, Query(alias="status")] = None,
    priority: TaskPriority | None = None,
    due_from: date | None = None,
    due_to: date | None = None,
    limit: PageLimit = None,
    offset: PageOffset = 0,
):
    items, has_more = page_items(
        session,
        "task",
        {
            "project_id": project_id,
            "deliverable_id": deliverable_id,
            "status": task_status,
            "priority": priority,
            "due_at_from": due_from,
            "due_at_to": due_to,
        },
        limit,
        offset,
    )
    set_page_links(response, request, limit, offset, has_more)
    return items


@router.get("/api/v1/tasks/{entity_id}", response_model=TaskRead, tags=["tasks"])
def get_task(entity_id: str, session: DbSession):
    return get_record(session, "task", entity_id)


@router.patch("/api/v1/tasks/{entity_id}", response_model=TaskRead, tags=["tasks"])
def update_task(entity_id: str, payload: TaskUpdate, session: DbSession):
    if payload.status == "done":
        raise HTTPException(status_code=422, detail="Use the task completion endpoint")
    if payload.status == "in_progress":
        raise HTTPException(status_code=422, detail="Use the task start endpoint")
    return update_record(session, "task", entity_id, payload)


@router.post("/api/v1/tasks/{entity_id}/start", response_model=TaskRead, tags=["tasks"])
def start_task(entity_id: str, session: DbSession):
    try:
        return store(session).start_task(entity_id)
    except DomainRuleError as exc:
        session.rollback()
        raise domain_http_error(exc) from exc


@router.post(
    "/api/v1/tasks/{entity_id}/work-logs",
    response_model=WorkLogRead,
    status_code=201,
    tags=["tasks"],
)
def add_task_work_log(entity_id: str, payload: WorkLogCreate, session: DbSession):
    try:
        return store(session).add_work_log(
            entity_id,
            minutes=payload.minutes,
            summary=payload.summary,
            started_at=payload.started_at,
        )
    except DomainRuleError as exc:
        session.rollback()
        raise domain_http_error(exc) from exc
    except IntegrityError as exc:
        session.rollback()
        raise HTTPException(status_code=409, detail="Work-log conflict") from exc


@router.get(
    "/api/v1/tasks/{entity_id}/work-logs",
    response_model=list[WorkLogRead],
    tags=["tasks"],
)
def list_task_work_logs(entity_id: str, session: DbSession):
    try:
        return store(session).list_task_work_logs(entity_id)
    except DomainRuleError as exc:
        raise domain_http_error(exc) from exc


@router.post("/api/v1/tasks/{entity_id}/complete", response_model=TaskRead, tags=["tasks"])
def complete_task(entity_id: str, payload: TaskComplete, session: DbSession):
    try:
        return store(session).complete_task(entity_id, payload.completion_note)
    except DomainRuleError as exc:
        session.rollback()
        raise domain_http_error(exc) from exc


@router.delete("/api/v1/tasks/{entity_id}", status_code=204, tags=["tasks"])
def delete_task(entity_id: str, session: DbSession):
    return delete_record(session, "task", entity_id)