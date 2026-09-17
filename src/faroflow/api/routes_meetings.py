from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, Request, Response
from sqlalchemy.exc import IntegrityError

from faroflow.schemas import (
    ActionItemCreate,
    ActionItemRead,
    ActionItemStatus,
    ActionItemToTask,
    ActionItemUpdate,
    EntityId,
    MeetingCreate,
    MeetingPreparation,
    MeetingRead,
    MeetingReview,
    MeetingStatus,
    MeetingUpdate,
    TaskRead,
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
from .routes_integrations import _drive_link_read

router = APIRouter()


@router.post("/api/v1/meetings", response_model=MeetingRead, status_code=201, tags=["meetings"])
def create_meeting(payload: MeetingCreate, session: DbSession):
    return create_record(session, "meeting", payload)


@router.get("/api/v1/meetings", response_model=list[MeetingRead], tags=["meetings"])
def list_meetings(
    session: DbSession,
    response: Response,
    request: Request,
    project_id: EntityId | None = None,
    meeting_status: Annotated[MeetingStatus | None, Query(alias="status")] = None,
    starts_from: datetime | None = None,
    starts_to: datetime | None = None,
    limit: PageLimit = None,
    offset: PageOffset = 0,
):
    items, has_more = page_items(
        session,
        "meeting",
        {
            "project_id": project_id,
            "status": meeting_status,
            "starts_at_from": starts_from,
            "starts_at_to": starts_to,
        },
        limit,
        offset,
    )
    set_page_links(response, request, limit, offset, has_more)
    return items


@router.get("/api/v1/meetings/{entity_id}", response_model=MeetingRead, tags=["meetings"])
def get_meeting(entity_id: str, session: DbSession):
    return get_record(session, "meeting", entity_id)


@router.patch("/api/v1/meetings/{entity_id}", response_model=MeetingRead, tags=["meetings"])
def update_meeting(entity_id: str, payload: MeetingUpdate, session: DbSession):
    return update_record(session, "meeting", entity_id, payload)


@router.delete("/api/v1/meetings/{entity_id}", status_code=204, tags=["meetings"])
def delete_meeting(entity_id: str, session: DbSession):
    return delete_record(session, "meeting", entity_id)


@router.post(
    "/api/v1/meetings/{meeting_id}/complete",
    response_model=MeetingRead,
    tags=["meetings"],
)
def complete_meeting(meeting_id: str, session: DbSession):
    try:
        return store(session).complete_meeting(meeting_id)
    except DomainRuleError as exc:
        session.rollback()
        raise domain_http_error(exc) from exc


@router.post(
    "/api/v1/meetings/{meeting_id}/review",
    response_model=MeetingRead,
    tags=["meetings"],
)
def review_meeting(meeting_id: str, _payload: MeetingReview, session: DbSession):
    try:
        return store(session).review_meeting(meeting_id)
    except DomainRuleError as exc:
        session.rollback()
        raise domain_http_error(exc) from exc


@router.get(
    "/api/v1/integrations/meetings/completed",
    response_model=list[MeetingRead],
    tags=["integrations"],
)
def completed_meeting_queue(
    session: DbSession,
    request: Request,
    response: Response,
    limit: PageLimit = None,
    offset: PageOffset = 0,
):
    items, has_more = store(session).list_completed_meetings(limit, offset)
    set_page_links(response, request, limit, offset, has_more)
    return items


@router.get(
    "/api/v1/meetings/{meeting_id}/preparation",
    response_model=MeetingPreparation,
    tags=["meetings"],
)
def prepare_meeting(meeting_id: str, session: DbSession):
    try:
        preparation = store(session).meeting_preparation(meeting_id)
    except DomainRuleError as exc:
        session.rollback()
        raise domain_http_error(exc) from exc
    preparation["artifact_links"] = [
        _drive_link_read(session, identity) for identity in preparation["artifact_links"]
    ]
    return preparation


@router.post(
    "/api/v1/action-items",
    response_model=ActionItemRead,
    status_code=201,
    tags=["action-items"],
)
def create_action_item(payload: ActionItemCreate, session: DbSession):
    return create_record(session, "action_item", payload)


@router.get("/api/v1/action-items", response_model=list[ActionItemRead], tags=["action-items"])
def list_action_items(
    session: DbSession,
    response: Response,
    request: Request,
    meeting_id: EntityId | None = None,
    item_status: Annotated[ActionItemStatus | None, Query(alias="status")] = None,
    limit: PageLimit = None,
    offset: PageOffset = 0,
):
    items, has_more = page_items(
        session,
        "action_item",
        {"meeting_id": meeting_id, "status": item_status},
        limit,
        offset,
    )
    set_page_links(response, request, limit, offset, has_more)
    return items


@router.get(
    "/api/v1/action-items/{entity_id}",
    response_model=ActionItemRead,
    tags=["action-items"],
)
def get_action_item(entity_id: str, session: DbSession):
    return get_record(session, "action_item", entity_id)


@router.patch(
    "/api/v1/action-items/{entity_id}",
    response_model=ActionItemRead,
    tags=["action-items"],
)
def update_action_item(entity_id: str, payload: ActionItemUpdate, session: DbSession):
    return update_record(session, "action_item", entity_id, payload)


@router.post(
    "/api/v1/action-items/{entity_id}/task",
    response_model=TaskRead,
    status_code=201,
    tags=["action-items"],
)
def action_item_to_task(entity_id: str, payload: ActionItemToTask, session: DbSession):
    try:
        return store(session).create_task_from_action(
            entity_id,
            payload.task_id,
            payload.priority,
            payload.due_at,
            payload.deliverable_id,
        )
    except DomainRuleError as exc:
        session.rollback()
        raise domain_http_error(exc) from exc
    except IntegrityError as exc:
        session.rollback()
        raise HTTPException(status_code=409, detail="Record or relationship conflict") from exc


@router.delete("/api/v1/action-items/{entity_id}", status_code=204, tags=["action-items"])
def delete_action_item(entity_id: str, session: DbSession):
    return delete_record(session, "action_item", entity_id)