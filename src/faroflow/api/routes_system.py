from datetime import date
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, Request, Response
from sqlalchemy.exc import IntegrityError

from faroflow import __version__
from faroflow.audit import list_audit_events_page
from faroflow.config import get_settings
from faroflow.portability import export_snapshot, import_snapshot
from faroflow.schemas import (
    AuditEventRead,
    EntityId,
    EntityKind,
    EveningClose,
    MorningBrief,
    ProgressSummary,
    SnapshotDocument,
    SnapshotImportResult,
)
from faroflow.services import DomainRuleError

from .deps import (
    DbSession,
    PageLimit,
    PageOffset,
    domain_http_error,
    set_page_links,
    store,
)

router = APIRouter()


@router.get("/health", tags=["system"])
def health() -> dict[str, str]:
    return {"status": "ok", "version": __version__}


@router.get("/api/v1/briefs/morning", response_model=MorningBrief, tags=["briefs"])
def morning_brief(
    session: DbSession,
    brief_date: Annotated[date | None, Query(alias="date")] = None,
    due_soon_days: Annotated[int, Query(ge=0, le=30)] = 3,
):
    try:
        return store(session).morning_brief(
            get_settings().app_timezone,
            brief_date=brief_date,
            due_soon_days=due_soon_days,
        )
    except DomainRuleError as exc:
        raise domain_http_error(exc) from exc


@router.get("/api/v1/briefs/evening", response_model=EveningClose, tags=["briefs"])
def evening_close(
    session: DbSession,
    close_date: Annotated[date | None, Query(alias="date")] = None,
):
    try:
        return store(session).evening_close(
            get_settings().app_timezone,
            close_date=close_date,
        )
    except DomainRuleError as exc:
        raise domain_http_error(exc) from exc


@router.get("/api/v1/reports/progress", response_model=ProgressSummary, tags=["reports"])
def progress_summary(
    session: DbSession,
    as_of: date | None = None,
    work_from: date | None = None,
    work_to: date | None = None,
):
    try:
        return store(session).progress_summary(
            get_settings().app_timezone,
            as_of=as_of,
            work_from=work_from,
            work_to=work_to,
        )
    except DomainRuleError as exc:
        raise domain_http_error(exc) from exc


@router.get("/api/v1/audit-events", response_model=list[AuditEventRead], tags=["audit"])
def get_audit_events(
    session: DbSession,
    response: Response,
    request: Request,
    entity_kind: EntityKind | None = None,
    entity_id: EntityId | None = None,
    actor: Annotated[str | None, Query(max_length=200)] = None,
    limit: PageLimit = None,
    offset: PageOffset = 0,
):
    events, has_more = list_audit_events_page(
        session,
        entity_kind=entity_kind,
        entity_id=entity_id,
        actor=actor,
        limit=limit,
        offset=offset,
    )
    set_page_links(response, request, limit, offset, has_more)
    return events


@router.get("/api/v1/snapshots/export", response_model=SnapshotDocument, tags=["snapshots"])
def export_portable_snapshot(session: DbSession):
    return export_snapshot(session)


@router.post(
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
        raise domain_http_error(exc) from exc
    except IntegrityError as exc:
        session.rollback()
        raise HTTPException(status_code=409, detail="Snapshot relationship conflict") from exc