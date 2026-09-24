from typing import Annotated, Any
from urllib.parse import urlencode

from fastapi import Depends, HTTPException, Query, Request, Response, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from faroflow.classification import (
    ClassifierAdapter,
    ClassifierNotConfigured,
    build_capture_classifier,
)
from faroflow.config import get_settings
from faroflow.db import get_session
from faroflow.services import DomainRuleError, DomainStore

RawDbSession = Annotated[Session, Depends(get_session)]


def request_session(request: Request, session: RawDbSession) -> Session:
    actor = (request.headers.get("X-Actor") or "local-user").strip()
    session.info["actor"] = actor[:200] or "local-user"
    return session


DbSession = Annotated[Session, Depends(request_session)]


def require_integration_operation_key(request: Request) -> None:
    """Gate protected integration operations behind an explicit shared key.

    When ``INTEGRATION_OPERATIONS_ENABLED`` is false the gate is open so local single-user
    runs behave as before. When enabled, every protected endpoint requires the matching
    ``X-Integration-Key`` header; the key never leaves the server except in the header check.
    """
    settings = get_settings()
    if not settings.integration_operations_enabled:
        return
    expected = (
        settings.integration_operation_key.get_secret_value()
        if settings.integration_operation_key
        else ""
    )
    provided = request.headers.get("X-Integration-Key") or ""
    if not expected or provided != expected:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="A valid integration operation key is required",
        )


ProtectedIntegrationOp = Annotated[None, Depends(require_integration_operation_key)]


def capture_classifier() -> ClassifierAdapter:
    try:
        return build_capture_classifier()
    except ClassifierNotConfigured as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


CaptureClassifier = Annotated[ClassifierAdapter, Depends(capture_classifier)]

PageLimit = Annotated[int | None, Query(ge=1, le=500)]
PageOffset = Annotated[int, Query(ge=0)]


def store(session: Session) -> DomainStore:
    return DomainStore(session)


def page_items(
    session: Session,
    kind: str,
    filters: dict[str, Any],
    limit: int | None,
    offset: int,
) -> tuple[list[Any], bool]:
    return store(session).list_page(kind, limit=limit, offset=offset, **filters)


def set_page_links(
    response: Response,
    request: Request,
    limit: int | None,
    offset: int,
    has_more: bool,
) -> None:
    if limit is None:
        return
    base = str(request.url).split("?", 1)[0]
    params = dict(request.query_params)
    links: list[str] = []
    if has_more:
        next_params = dict(params)
        next_params["offset"] = str(offset + limit)
        links.append(f'<{base}?{urlencode(next_params)}>; rel="next"')
    if offset > 0:
        prev_params = dict(params)
        prev_params["offset"] = str(max(offset - limit, 0))
        links.append(f'<{base}?{urlencode(prev_params)}>; rel="prev"')
    if links:
        response.headers["Link"] = ", ".join(links)


def domain_http_error(exc: DomainRuleError) -> HTTPException:
    return HTTPException(status_code=exc.status_code, detail=str(exc))


def create_record(session: Session, kind: str, payload) -> Any:
    try:
        return store(session).create(kind, **payload.model_dump())
    except DomainRuleError as exc:
        session.rollback()
        raise domain_http_error(exc) from exc
    except IntegrityError as exc:
        session.rollback()
        raise HTTPException(status_code=409, detail="Record or relationship conflict") from exc


def get_record(session: Session, kind: str, entity_id: str) -> Any:
    entity = store(session).get(kind, entity_id)
    if entity is None:
        raise HTTPException(status_code=404, detail=f"{kind} not found")
    return entity


def update_record(session: Session, kind: str, entity_id: str, payload) -> Any:
    try:
        return store(session).update(kind, entity_id, **payload.model_dump(exclude_unset=True))
    except DomainRuleError as exc:
        session.rollback()
        raise domain_http_error(exc) from exc
    except IntegrityError as exc:
        session.rollback()
        raise HTTPException(status_code=409, detail="Record or relationship conflict") from exc


def delete_record(session: Session, kind: str, entity_id: str) -> Response:
    try:
        store(session).delete(kind, entity_id)
    except DomainRuleError as exc:
        raise domain_http_error(exc) from exc
    except IntegrityError as exc:
        session.rollback()
        raise HTTPException(status_code=409, detail="Record is still referenced") from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)