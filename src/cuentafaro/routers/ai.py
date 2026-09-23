"""API del asistente con IA (Fase 3): sugerencias, insights y propuestas.

La IA propone, la persona confirma: toda propuesta nace `pending` y solo una
resolución explícita la aplica o descarta.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from cuentafaro.deps import get_session
from cuentafaro.schemas import (
    AiInsightsResult,
    AiProposalResolve,
    AiProposalView,
    AiSuggestCategoryCreate,
    AiSuggestCategoryResult,
)
from cuentafaro.services import DomainRuleError, DomainStore

router = APIRouter(tags=["assistant"])
SessionDependency = Annotated[Session, Depends(get_session)]


@router.post(
    "/households/{household_id}/assistant/suggest-category",
    response_model=AiSuggestCategoryResult,
)
def suggest_category(
    household_id: str,
    payload: AiSuggestCategoryCreate,
    session: SessionDependency,
) -> dict:
    store = DomainStore(session)
    suggestions, proposal = store.ai_suggest_category(
        household_id=household_id,
        description=payload.description,
        amount=payload.amount,
    )
    return {
        "provider": "rule_based",
        "suggestions": suggestions,
        "proposal": AiProposalView.model_validate(proposal).model_dump(mode="json"),
    }


@router.get("/households/{household_id}/assistant/insights", response_model=AiInsightsResult)
def insights(
    household_id: str,
    session: SessionDependency,
    year: Annotated[int, Query(ge=2000, le=2100)] = 0,
    month: Annotated[int, Query(ge=1, le=12)] = 0,
) -> dict:
    store = DomainStore(session)
    today = _today()
    year = year or today.year
    month = month or today.month
    return store.ai_insights(household_id, year=year, month=month)


@router.get("/households/{household_id}/assistant/proposals", response_model=list[AiProposalView])
def list_proposals(
    household_id: str,
    session: SessionDependency,
    status: Annotated[str | None, Query()] = None,
) -> list[dict]:
    if status not in (None, "pending", "applied", "dismissed"):
        raise DomainRuleError("status debe ser pending, applied o dismissed")
    store = DomainStore(session)
    proposals = store.list_ai_proposals(household_id, status=status)
    return [AiProposalView.model_validate(item).model_dump(mode="json") for item in proposals]


@router.post("/assistant/proposals/{proposal_id}/resolve", response_model=AiProposalView)
def resolve_proposal(
    proposal_id: str,
    payload: AiProposalResolve,
    session: SessionDependency,
) -> dict:
    store = DomainStore(session)
    proposal = store.resolve_ai_proposal(proposal_id, resolution=payload.resolution)
    return AiProposalView.model_validate(proposal).model_dump(mode="json")


def _today():
    from datetime import date

    return date.today()
