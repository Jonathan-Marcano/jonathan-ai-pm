from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from cuentafaro.deps import get_session
from cuentafaro.schemas import AuditEventView
from cuentafaro.services import DomainStore

router = APIRouter(tags=["audit"])
SessionDependency = Annotated[Session, Depends(get_session)]


@router.get("/audit", response_model=list[AuditEventView])
def list_audit(
    session: SessionDependency,
    entity_kind: str | None = Query(default=None),
    entity_id: str | None = Query(default=None),
    action: str | None = Query(default=None),
    actor: str | None = Query(default=None),
    limit: int = Query(default=200, ge=1, le=1000),
) -> list[dict]:
    store = DomainStore(session)
    events = store.list_audit(
        entity_kind=entity_kind,
        entity_id=entity_id,
        action=action,
        actor=actor,
        limit=limit,
    )
    return [AuditEventView.model_validate(e).model_dump(mode="json") for e in events]
