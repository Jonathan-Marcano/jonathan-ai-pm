from datetime import date
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, Request, Response

from faroflow.schemas import (
    ClientCreate,
    ClientRead,
    ClientUpdate,
    DeliverableCreate,
    DeliverableRead,
    DeliverableStatus,
    DeliverableUpdate,
    EntityId,
    ProjectCreate,
    ProjectHealth,
    ProjectRead,
    ProjectStatus,
    ProjectUpdate,
    RecordStatus,
    WorkspaceCreate,
    WorkspaceRead,
    WorkspaceUpdate,
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


@router.post(
    "/api/v1/workspaces", response_model=WorkspaceRead, status_code=201, tags=["workspaces"]
)
def create_workspace(payload: WorkspaceCreate, session: DbSession):
    return create_record(session, "workspace", payload)


@router.get("/api/v1/workspaces", response_model=list[WorkspaceRead], tags=["workspaces"])
def list_workspaces(
    session: DbSession,
    response: Response,
    request: Request,
    record_status: Annotated[RecordStatus | None, Query(alias="status")] = None,
    limit: PageLimit = None,
    offset: PageOffset = 0,
):
    items, has_more = page_items(session, "workspace", {"status": record_status}, limit, offset)
    set_page_links(response, request, limit, offset, has_more)
    return items


@router.get("/api/v1/workspaces/{entity_id}", response_model=WorkspaceRead, tags=["workspaces"])
def get_workspace(entity_id: str, session: DbSession):
    return get_record(session, "workspace", entity_id)


@router.patch("/api/v1/workspaces/{entity_id}", response_model=WorkspaceRead, tags=["workspaces"])
def update_workspace(entity_id: str, payload: WorkspaceUpdate, session: DbSession):
    return update_record(session, "workspace", entity_id, payload)


@router.delete("/api/v1/workspaces/{entity_id}", status_code=204, tags=["workspaces"])
def delete_workspace(entity_id: str, session: DbSession):
    return delete_record(session, "workspace", entity_id)


@router.post("/api/v1/clients", response_model=ClientRead, status_code=201, tags=["clients"])
def create_client(payload: ClientCreate, session: DbSession):
    return create_record(session, "client", payload)


@router.get("/api/v1/clients", response_model=list[ClientRead], tags=["clients"])
def list_clients(
    session: DbSession,
    response: Response,
    request: Request,
    workspace_id: EntityId | None = None,
    record_status: Annotated[RecordStatus | None, Query(alias="status")] = None,
    limit: PageLimit = None,
    offset: PageOffset = 0,
):
    items, has_more = page_items(
        session,
        "client",
        {"workspace_id": workspace_id, "status": record_status},
        limit,
        offset,
    )
    set_page_links(response, request, limit, offset, has_more)
    return items


@router.get("/api/v1/clients/{entity_id}", response_model=ClientRead, tags=["clients"])
def get_client(entity_id: str, session: DbSession):
    return get_record(session, "client", entity_id)


@router.patch("/api/v1/clients/{entity_id}", response_model=ClientRead, tags=["clients"])
def update_client(entity_id: str, payload: ClientUpdate, session: DbSession):
    return update_record(session, "client", entity_id, payload)


@router.delete("/api/v1/clients/{entity_id}", status_code=204, tags=["clients"])
def delete_client(entity_id: str, session: DbSession):
    return delete_record(session, "client", entity_id)


@router.post("/api/v1/projects", response_model=ProjectRead, status_code=201, tags=["projects"])
def create_project(payload: ProjectCreate, session: DbSession):
    return create_record(session, "project", payload)


@router.get("/api/v1/projects", response_model=list[ProjectRead], tags=["projects"])
def list_projects(
    session: DbSession,
    response: Response,
    request: Request,
    client_id: EntityId | None = None,
    project_status: Annotated[ProjectStatus | None, Query(alias="status")] = None,
    health: ProjectHealth | None = None,
    limit: PageLimit = None,
    offset: PageOffset = 0,
):
    items, has_more = page_items(
        session,
        "project",
        {"client_id": client_id, "status": project_status, "health": health},
        limit,
        offset,
    )
    set_page_links(response, request, limit, offset, has_more)
    return items


@router.get("/api/v1/projects/{entity_id}", response_model=ProjectRead, tags=["projects"])
def get_project(entity_id: str, session: DbSession):
    return get_record(session, "project", entity_id)


@router.patch("/api/v1/projects/{entity_id}", response_model=ProjectRead, tags=["projects"])
def update_project(entity_id: str, payload: ProjectUpdate, session: DbSession):
    return update_record(session, "project", entity_id, payload)


@router.delete("/api/v1/projects/{entity_id}", status_code=204, tags=["projects"])
def delete_project(entity_id: str, session: DbSession):
    return delete_record(session, "project", entity_id)


@router.post(
    "/api/v1/deliverables",
    response_model=DeliverableRead,
    status_code=201,
    tags=["deliverables"],
)
def create_deliverable(payload: DeliverableCreate, session: DbSession):
    if payload.status == "in_review":
        raise HTTPException(status_code=422, detail="Use the review transition endpoint")
    return create_record(session, "deliverable", payload)


@router.get("/api/v1/deliverables", response_model=list[DeliverableRead], tags=["deliverables"])
def list_deliverables(
    session: DbSession,
    response: Response,
    request: Request,
    project_id: EntityId | None = None,
    deliverable_status: Annotated[DeliverableStatus | None, Query(alias="status")] = None,
    due_from: date | None = None,
    due_to: date | None = None,
    limit: PageLimit = None,
    offset: PageOffset = 0,
):
    items, has_more = page_items(
        session,
        "deliverable",
        {
            "project_id": project_id,
            "status": deliverable_status,
            "due_at_from": due_from,
            "due_at_to": due_to,
        },
        limit,
        offset,
    )
    set_page_links(response, request, limit, offset, has_more)
    return items


@router.get(
    "/api/v1/deliverables/{entity_id}",
    response_model=DeliverableRead,
    tags=["deliverables"],
)
def get_deliverable(entity_id: str, session: DbSession):
    return get_record(session, "deliverable", entity_id)


@router.patch(
    "/api/v1/deliverables/{entity_id}",
    response_model=DeliverableRead,
    tags=["deliverables"],
)
def update_deliverable(entity_id: str, payload: DeliverableUpdate, session: DbSession):
    if payload.status == "in_review":
        raise HTTPException(status_code=422, detail="Use the review transition endpoint")
    return update_record(session, "deliverable", entity_id, payload)


@router.post(
    "/api/v1/deliverables/{entity_id}/review",
    response_model=DeliverableRead,
    tags=["deliverables"],
)
def review_deliverable(entity_id: str, session: DbSession):
    try:
        return store(session).move_deliverable_to_review(entity_id)
    except DomainRuleError as exc:
        session.rollback()
        raise domain_http_error(exc) from exc


@router.delete("/api/v1/deliverables/{entity_id}", status_code=204, tags=["deliverables"])
def delete_deliverable(entity_id: str, session: DbSession):
    return delete_record(session, "deliverable", entity_id)