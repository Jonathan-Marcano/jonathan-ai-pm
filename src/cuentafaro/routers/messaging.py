"""API de capturas por mensajería (Fase 4, CF4-03 a CF4-05).

Las capturas entran **pendientes**. La extracción (CF4-04) propone fecha,
monto y descripción con OCR local; la persona corrige y luego confirma
(CF4-05), momento en que se persiste el movimiento. Nada se aplica solo.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from cuentafaro.deps import get_session
from cuentafaro.schemas import (
    CaptureConfirm,
    CaptureCreate,
    CaptureProposalUpdate,
    CaptureResolve,
    CaptureView,
)
from cuentafaro.services import DomainRuleError, DomainStore

router = APIRouter(tags=["captures"])
SessionDependency = Annotated[Session, Depends(get_session)]


@router.post("/households/{household_id}/captures", response_model=CaptureView, status_code=201)
def create_capture(
    household_id: str,
    payload: CaptureCreate,
    session: SessionDependency,
) -> dict:
    store = DomainStore(session)
    capture = store.create_capture(
        household_id=household_id,
        kind=payload.kind,
        raw_text=payload.raw_text,
        payload=payload.payload,
        channel=payload.channel,
    )
    return CaptureView.model_validate(capture).model_dump(mode="json")


@router.get("/households/{household_id}/captures", response_model=list[CaptureView])
def list_captures(
    household_id: str,
    session: SessionDependency,
    status: Annotated[str | None, Query()] = None,
) -> list[dict]:
    if status not in (None, "pending", "needs_input", "confirmed", "rejected", "discarded"):
        raise DomainRuleError("status es inválido")
    store = DomainStore(session)
    captures = store.list_captures(household_id, status=status)
    return [CaptureView.model_validate(item).model_dump(mode="json") for item in captures]


@router.get("/captures/{capture_id}", response_model=CaptureView)
def get_capture(capture_id: str, session: SessionDependency) -> dict:
    store = DomainStore(session)
    capture = store.get_capture(capture_id)
    return CaptureView.model_validate(capture).model_dump(mode="json")


@router.post("/captures/{capture_id}/resolve", response_model=CaptureView)
def resolve_capture(
    capture_id: str,
    payload: CaptureResolve,
    session: SessionDependency,
) -> dict:
    store = DomainStore(session)
    capture = store.resolve_capture(capture_id, resolution=payload.resolution)
    return CaptureView.model_validate(capture).model_dump(mode="json")


@router.post("/captures/{capture_id}/process", response_model=CaptureView)
def process_capture(capture_id: str, session: SessionDependency) -> dict:
    """CF4-04: extrae texto (texto directo u OCR local) y arma la propuesta."""
    store = DomainStore(session)
    capture = store.analyze_capture(capture_id)
    return CaptureView.model_validate(capture).model_dump(mode="json")


@router.post("/captures/{capture_id}/proposal", response_model=CaptureView)
def update_capture_proposal(
    capture_id: str,
    payload: CaptureProposalUpdate,
    session: SessionDependency,
) -> dict:
    """CF4-05: corrige fecha/monto/descripción/categoría de la propuesta."""
    store = DomainStore(session)
    capture = store.update_capture_proposal(
        capture_id,
        date=payload.date.isoformat() if payload.date else None,
        amount=payload.amount,
        description=payload.description,
        category_id=payload.category_id,
    )
    return CaptureView.model_validate(capture).model_dump(mode="json")


@router.post("/captures/{capture_id}/confirm", response_model=CaptureView)
def confirm_capture(
    capture_id: str,
    payload: CaptureConfirm,
    session: SessionDependency,
) -> dict:
    """CF4-05: confirmación humana; persiste el movimiento y liga la captura."""
    store = DomainStore(session)
    capture = store.confirm_capture(
        capture_id,
        account_id=payload.account_id,
        amount=payload.amount,
        capture_date=payload.date.isoformat() if payload.date else None,
        description=payload.description,
        category_id=payload.category_id,
    )
    return CaptureView.model_validate(capture).model_dump(mode="json")
