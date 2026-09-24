from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, Request, Response, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from faroflow.integrations.contracts import CalendarWindow, IntegrationContractError
from faroflow.integrations.google_calendar import (
    GoogleCalendarNotConfigured,
    build_google_calendar_adapter,
)
from faroflow.integrations.google_drive import (
    GoogleDriveNotConfigured,
    build_google_drive_adapter,
)
from faroflow.integrations.persistence import IntegrationStateError, IntegrationStateStore
from faroflow.integrations.reconciliation import (
    ingest_inbound_messages,
    reconcile_calendar_events,
    reconcile_drive_files,
)
from faroflow.integrations.telegram_messaging import (
    TelegramMessagingNotConfigured,
    build_telegram_messaging_adapter,
)
from faroflow.models import Deliverable, ExternalIdentity, SyncRun
from faroflow.schemas import (
    DriveFileLinkCreate,
    DriveLinkRead,
    MeetingProjectAssociate,
    MeetingProjectMappingRead,
    MeetingRead,
    SyncRunErrorRead,
    SyncRunRead,
)
from faroflow.services import DomainRuleError

from .deps import (
    DbSession,
    PageLimit,
    PageOffset,
    ProtectedIntegrationOp,
    domain_http_error,
    set_page_links,
    store,
)

router = APIRouter()


def _drive_link_read(session: Session, identity: ExternalIdentity) -> dict:
    title = session.scalar(select(Deliverable.title).where(Deliverable.id == identity.entity_id))
    return {
        "id": identity.id,
        "deliverable_id": identity.entity_id,
        "deliverable_title": title or identity.entity_id,
        "source_system": identity.source_system,
        "external_id": identity.external_id,
        "external_name": identity.external_name,
        "web_url": identity.web_url,
        "mime_type": identity.mime_type,
        "external_version": identity.external_version,
        "external_modified_at": identity.external_modified_at,
        "last_synced_at": identity.last_synced_at,
        "created_at": identity.created_at,
        "updated_at": identity.updated_at,
    }


@router.get(
    "/api/v1/integrations/meetings/unmatched",
    response_model=list[MeetingRead],
    tags=["integrations"],
)
def review_queue(
    session: DbSession,
    request: Request,
    response: Response,
    limit: PageLimit = None,
    offset: PageOffset = 0,
):
    items, has_more = store(session).list_meetings_without_project(limit, offset)
    set_page_links(response, request, limit, offset, has_more)
    return items


@router.post(
    "/api/v1/integrations/meetings/{meeting_id}/project",
    response_model=MeetingRead,
    tags=["integrations"],
)
def confirm_project(
    meeting_id: str,
    payload: MeetingProjectAssociate,
    session: DbSession,
    _op: ProtectedIntegrationOp,
):
    try:
        return store(session).associate_meeting(meeting_id, payload.project_id)
    except DomainRuleError as exc:
        session.rollback()
        raise domain_http_error(exc) from exc
    except IntegrityError as exc:
        session.rollback()
        raise HTTPException(status_code=409, detail="Record or relationship conflict") from exc


@router.get(
    "/api/v1/integrations/meeting-project-mappings",
    response_model=list[MeetingProjectMappingRead],
    tags=["integrations"],
)
def list_mappings(
    session: DbSession,
    request: Request,
    response: Response,
    limit: PageLimit = None,
    offset: PageOffset = 0,
):
    state = IntegrationStateStore(session)
    items, has_more = state.list_project_mappings(limit, offset)
    set_page_links(response, request, limit, offset, has_more)
    return items


@router.delete(
    "/api/v1/integrations/meeting-project-mappings/{mapping_id}",
    status_code=204,
    tags=["integrations"],
)
def delete_mapping(mapping_id: str, session: DbSession, _op: ProtectedIntegrationOp):
    state = IntegrationStateStore(session)
    try:
        state.delete_project_mapping(mapping_id)
    except IntegrationStateError as exc:
        session.rollback()
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get(
    "/api/v1/integrations/drive-links",
    response_model=list[DriveLinkRead],
    tags=["integrations"],
)
def list_drive_links(
    session: DbSession,
    request: Request,
    response: Response,
    limit: PageLimit = None,
    offset: PageOffset = 0,
):
    state = IntegrationStateStore(session)
    items, has_more = state.list_deliverable_identities(
        source_system="google-drive", limit=limit, offset=offset
    )
    set_page_links(response, request, limit, offset, has_more)
    return [_drive_link_read(session, item) for item in items]


@router.post(
    "/api/v1/deliverables/{deliverable_id}/drive-link",
    response_model=DriveLinkRead,
    status_code=201,
    tags=["integrations"],
)
def link_drive_file(
    deliverable_id: str,
    payload: DriveFileLinkCreate,
    session: DbSession,
    _op: ProtectedIntegrationOp,
):
    try:
        identity = store(session).link_drive_file(
            deliverable_id,
            source_system=payload.source_system,
            external_id=payload.external_id,
            name=payload.name,
            web_url=str(payload.web_url) if payload.web_url else None,
            mime_type=payload.mime_type,
        )
    except DomainRuleError as exc:
        session.rollback()
        raise domain_http_error(exc) from exc
    except IntegrityError as exc:
        session.rollback()
        raise HTTPException(status_code=409, detail="Record or relationship conflict") from exc
    return _drive_link_read(session, identity)


@router.delete(
    "/api/v1/deliverables/{deliverable_id}/drive-link",
    status_code=204,
    tags=["integrations"],
)
def unlink_drive_file(
    deliverable_id: str, session: DbSession, _op: ProtectedIntegrationOp
):
    try:
        store(session).unlink_drive_file(deliverable_id)
    except DomainRuleError as exc:
        session.rollback()
        raise domain_http_error(exc) from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/api/v1/integrations/drive/refresh",
    response_model=SyncRunRead,
    tags=["integrations"],
)
def refresh_drive_metadata(
    session: DbSession,
    _op: ProtectedIntegrationOp,
    external_ids: Annotated[list[str] | None, Query()] = None,
):
    try:
        adapter = build_google_drive_adapter()
    except GoogleDriveNotConfigured as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    run = reconcile_drive_files(session, adapter=adapter, external_ids=external_ids)
    return run


@router.post(
    "/api/v1/integrations/calendar/sync",
    response_model=SyncRunRead,
    tags=["integrations"],
)
def sync_calendar(
    session: DbSession,
    _op: ProtectedIntegrationOp,
    starts_at: Annotated[datetime, Query()],
    ends_at: Annotated[datetime, Query()],
    project_id: Annotated[str | None, Query()] = None,
):
    try:
        window = CalendarWindow(starts_at=starts_at, ends_at=ends_at)
    except IntegrationContractError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    try:
        adapter = build_google_calendar_adapter()
    except GoogleCalendarNotConfigured as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    run = reconcile_calendar_events(
        session,
        project_id=project_id,
        adapter=adapter,
        window=window,
    )
    return run


@router.post(
    "/api/v1/integrations/messaging/inbound",
    response_model=SyncRunRead,
    tags=["integrations"],
)
def ingest_messaging(
    session: DbSession,
    _op: ProtectedIntegrationOp,
    conversation_ids: Annotated[list[str], Query(min_length=1)],
    since: Annotated[datetime, Query()],
):
    try:
        adapter = build_telegram_messaging_adapter()
    except TelegramMessagingNotConfigured as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return ingest_inbound_messages(
        session,
        adapter=adapter,
        conversation_ids=conversation_ids,
        since=since,
    )


def _restore_run_window(run: SyncRun) -> CalendarWindow:
    stripped = run.window_starts_at.replace(tzinfo=UTC)
    stripped_end = run.window_ends_at.replace(tzinfo=UTC)
    return CalendarWindow(starts_at=stripped, ends_at=stripped_end)


def _require_run(session: Session, run_id: str) -> SyncRun:
    run = session.get(SyncRun, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail=f"Synchronization run not found: {run_id}")
    return run


@router.get(
    "/api/v1/integrations/sync-runs",
    response_model=list[SyncRunRead],
    tags=["integrations"],
)
def list_sync_runs(
    session: DbSession,
    request: Request,
    response: Response,
    source_system: Annotated[str | None, Query()] = None,
    resource_kind: Annotated[str | None, Query()] = None,
    run_status: Annotated[str | None, Query(alias="status")] = None,
    limit: PageLimit = None,
    offset: PageOffset = 0,
):
    state = IntegrationStateStore(session)
    items, has_more = state.list_runs(
        source_system=source_system,
        resource_kind=resource_kind,
        status=run_status,
        limit=limit,
        offset=offset,
    )
    set_page_links(response, request, limit, offset, has_more)
    return items


@router.get(
    "/api/v1/integrations/sync-runs/{run_id}",
    response_model=SyncRunRead,
    tags=["integrations"],
)
def get_sync_run(run_id: str, session: DbSession):
    return _require_run(session, run_id)


@router.get(
    "/api/v1/integrations/sync-runs/{run_id}/errors",
    response_model=list[SyncRunErrorRead],
    tags=["integrations"],
)
def list_sync_run_errors(run_id: str, session: DbSession):
    _require_run(session, run_id)
    state = IntegrationStateStore(session)
    return state.list_errors(run_id)


@router.post(
    "/api/v1/integrations/sync-runs/{run_id}/retry",
    response_model=SyncRunRead,
    tags=["integrations"],
)
def retry_sync_run(
    run_id: str, session: DbSession, _op: ProtectedIntegrationOp
):
    run = _require_run(session, run_id)
    if run.resource_kind == "calendar":
        if run.window_starts_at is None or run.window_ends_at is None:
            raise HTTPException(
                status_code=422, detail="Synchronization run has no calendar window"
            )
        try:
            window = _restore_run_window(run)
        except IntegrationContractError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        try:
            adapter = build_google_calendar_adapter()
        except GoogleCalendarNotConfigured as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        return reconcile_calendar_events(session, adapter=adapter, window=window)
    if run.resource_kind == "message":
        raise HTTPException(
            status_code=422,
            detail="Messaging inbound runs are re-polled through the ingest endpoint",
        )
    try:
        adapter = build_google_drive_adapter()
    except GoogleDriveNotConfigured as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return reconcile_drive_files(session, adapter=adapter)