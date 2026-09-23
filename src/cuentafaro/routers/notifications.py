"""API de avisos programados (Fase 4, CF4-07/CF4-08).

El programador arma la cola de salida con las plantillas del dominio y entrega
los avisos vencidos por el proveedor configurado (simulado en este tramo); cada
envío queda auditado en ``notification_sends``.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from cuentafaro.deps import get_session
from cuentafaro.messaging import get_messaging_provider
from cuentafaro.notifications import run_household_notifications
from cuentafaro.schemas import (
    NotificationPreferenceUpdate,
    NotificationPreferenceView,
    NotificationRunResult,
    NotificationSendView,
    NotificationView,
)
from cuentafaro.services import DomainStore

router = APIRouter(tags=["notifications"])
SessionDependency = Annotated[Session, Depends(get_session)]


@router.get("/households/{household_id}/notifications", response_model=list[NotificationView])
def list_notifications(
    household_id: str,
    session: SessionDependency,
    status: Annotated[str | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
) -> list[dict]:
    store = DomainStore(session)
    rows = store.list_notifications(household_id, status=status, limit=limit)
    return [NotificationView.model_validate(row).model_dump(mode="json") for row in rows]


@router.get(
    "/households/{household_id}/notifications/sends", response_model=list[NotificationSendView]
)
def list_notification_sends(
    household_id: str,
    session: SessionDependency,
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
) -> list[dict]:
    store = DomainStore(session)
    rows = store.list_notification_sends(household_id, limit=limit)
    return [NotificationSendView.model_validate(row).model_dump(mode="json") for row in rows]


@router.post("/households/{household_id}/notifications/run", response_model=NotificationRunResult)
def run_notifications(
    household_id: str,
    session: SessionDependency,
) -> dict:
    """Encola lo programado para hoy y entrega lo que ya venció (CF4-07)."""
    provider = get_messaging_provider()
    return run_household_notifications(session, provider, household_id)


@router.get(
    "/households/{household_id}/notification-preferences",
    response_model=list[NotificationPreferenceView],
)
def list_notification_preferences(
    household_id: str,
    session: SessionDependency,
) -> list[dict]:
    store = DomainStore(session)
    rows = store.get_notification_preferences(household_id)
    return [NotificationPreferenceView.model_validate(row).model_dump(mode="json") for row in rows]


@router.patch(
    "/households/{household_id}/notification-preferences",
    response_model=list[NotificationPreferenceView],
)
def update_notification_preference(
    household_id: str,
    payload: NotificationPreferenceUpdate,
    session: SessionDependency,
) -> list[dict]:
    store = DomainStore(session)
    rows = store.set_notification_preference(
        household_id, template_kind=payload.template_kind, enabled=payload.enabled
    )
    return [NotificationPreferenceView.model_validate(row).model_dump(mode="json") for row in rows]
