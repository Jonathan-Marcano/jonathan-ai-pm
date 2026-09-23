from typing import Annotated

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from cuentafaro.deps import get_session
from cuentafaro.services import DomainStore

router = APIRouter(tags=["dashboard"])
SessionDependency = Annotated[Session, Depends(get_session)]


class PeriodClose(BaseModel):
    year: int = Field(ge=2000, le=2100)
    month: int = Field(ge=1, le=12)


@router.get("/households/{household_id}/dashboard")
def dashboard(
    household_id: str,
    session: SessionDependency,
    year: int = Query(ge=2000, le=2100),
    month: int = Query(ge=1, le=12),
) -> dict:
    store = DomainStore(session)
    return store.dashboard(household_id, year=year, month=month)


@router.get("/households/{household_id}/upcoming-payments")
def upcoming_payments(
    household_id: str,
    session: SessionDependency,
    days: int = Query(default=30, ge=1, le=120),
) -> dict:
    store = DomainStore(session)
    return store.upcoming_payments(household_id, days=days)


@router.get("/households/{household_id}/debt-summary")
def debt_summary(household_id: str, session: SessionDependency) -> dict:
    store = DomainStore(session)
    return store.debt_summary(household_id)


@router.get("/households/{household_id}/net-worth")
def net_worth(household_id: str, session: SessionDependency) -> dict:
    store = DomainStore(session)
    return store.net_worth(household_id)


@router.post("/households/{household_id}/monthly-close")
def monthly_close(household_id: str, payload: PeriodClose, session: SessionDependency) -> dict:
    store = DomainStore(session)
    return store.monthly_close(household_id, year=payload.year, month=payload.month)
