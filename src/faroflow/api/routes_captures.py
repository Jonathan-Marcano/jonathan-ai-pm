from fastapi import APIRouter, HTTPException, Request, Response
from sqlalchemy.exc import IntegrityError

from faroflow.classification import ClassifierError
from faroflow.schemas import (
    CaptureApply,
    CaptureCreate,
    CaptureDisposition,
    CaptureRead,
    CaptureStatus,
    CaptureTriage,
    EntityId,
)
from faroflow.services import DomainRuleError

from .deps import (
    CaptureClassifier,
    DbSession,
    PageLimit,
    PageOffset,
    domain_http_error,
    get_record,
    page_items,
    set_page_links,
    store,
)

router = APIRouter()


@router.post("/api/v1/captures", response_model=CaptureRead, status_code=201, tags=["captures"])
def create_capture(payload: CaptureCreate, session: DbSession):
    try:
        return store(session).capture(payload.text)
    except IntegrityError as exc:
        session.rollback()
        raise HTTPException(status_code=409, detail="Capture conflict") from exc


@router.get("/api/v1/captures", response_model=list[CaptureRead], tags=["captures"])
def list_captures(
    session: DbSession,
    response: Response,
    request: Request,
    capture_status: CaptureStatus | None = None,
    disposition: CaptureDisposition | None = None,
    project_id: EntityId | None = None,
    limit: PageLimit = None,
    offset: PageOffset = 0,
):
    items, has_more = page_items(
        session,
        "capture",
        {"status": capture_status, "disposition": disposition, "project_id": project_id},
        limit,
        offset,
    )
    set_page_links(response, request, limit, offset, has_more)
    return items


@router.get("/api/v1/captures/{entity_id}", response_model=CaptureRead, tags=["captures"])
def get_capture(entity_id: EntityId, session: DbSession):
    return get_record(session, "capture", entity_id)


@router.post(
    "/api/v1/captures/{entity_id}/suggest",
    response_model=CaptureRead,
    tags=["captures"],
)
def suggest_capture(
    entity_id: EntityId,
    classifier: CaptureClassifier,
    session: DbSession,
):
    """Attach a read-only classification proposal without binding the capture."""
    try:
        return store(session).suggest_capture(entity_id, classifier=classifier)
    except ClassifierError as exc:
        session.rollback()
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except DomainRuleError as exc:
        session.rollback()
        raise domain_http_error(exc) from exc


@router.post(
    "/api/v1/captures/{entity_id}/apply",
    response_model=CaptureRead,
    tags=["captures"],
)
def apply_capture(
    entity_id: EntityId,
    session: DbSession,
    payload: CaptureApply | None = None,
):
    """Confirm a pending proposal and create the operational record from it."""
    try:
        return store(session).apply_capture(
            entity_id,
            meeting_id=payload.meeting_id if payload else None,
        )
    except DomainRuleError as exc:
        session.rollback()
        raise domain_http_error(exc) from exc
    except IntegrityError as exc:
        session.rollback()
        raise HTTPException(status_code=409, detail="Record or relationship conflict") from exc


@router.post("/api/v1/captures/{entity_id}/triage", response_model=CaptureRead, tags=["captures"])
def triage_capture(entity_id: EntityId, payload: CaptureTriage, session: DbSession):
    try:
        return store(session).triage_capture(
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
        raise domain_http_error(exc) from exc
    except IntegrityError as exc:
        session.rollback()
        raise HTTPException(status_code=409, detail="Record or relationship conflict") from exc