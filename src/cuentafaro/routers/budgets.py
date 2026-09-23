from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from cuentafaro.deps import get_session
from cuentafaro.schemas import (
    BudgetCategorySet,
    BudgetCategoryView,
    BudgetCreate,
    BudgetUpdate,
    BudgetView,
)
from cuentafaro.services import DomainStore

router = APIRouter(tags=["budgets"])
SessionDependency = Annotated[Session, Depends(get_session)]


@router.post("/households/{household_id}/budgets", response_model=BudgetView, status_code=201)
def create_budget(household_id: str, payload: BudgetCreate, session: SessionDependency) -> dict:
    store = DomainStore(session)
    budget = store.create_budget(
        household_id, year=payload.year, month=payload.month, status=payload.status
    )
    return BudgetView.model_validate(budget).model_dump(mode="json")


@router.get("/households/{household_id}/budgets", response_model=list[BudgetView])
def list_budgets(household_id: str, session: SessionDependency) -> list[dict]:
    store = DomainStore(session)
    budgets = store.list_budgets(household_id)
    return [BudgetView.model_validate(b).model_dump(mode="json") for b in budgets]


@router.get("/budgets/{budget_id}", response_model=BudgetView)
def get_budget(budget_id: str, session: SessionDependency) -> dict:
    store = DomainStore(session)
    budget = store.get_budget(budget_id)
    return BudgetView.model_validate(budget).model_dump(mode="json")


@router.patch("/budgets/{budget_id}", response_model=BudgetView)
def update_budget(budget_id: str, payload: BudgetUpdate, session: SessionDependency) -> dict:
    store = DomainStore(session)
    budget = store.update_budget(budget_id, status=payload.status)
    return BudgetView.model_validate(budget).model_dump(mode="json")


@router.post("/budgets/{budget_id}/categories", response_model=BudgetCategoryView, status_code=201)
def set_budget_category(
    budget_id: str, payload: BudgetCategorySet, session: SessionDependency
) -> dict:
    store = DomainStore(session)
    budget_category = store.set_budget_category(
        budget_id, category_id=payload.category_id, planned_amount=payload.planned_amount
    )
    return BudgetCategoryView.model_validate(budget_category).model_dump(mode="json")


@router.get("/budgets/{budget_id}/categories", response_model=list[BudgetCategoryView])
def list_budget_categories(budget_id: str, session: SessionDependency) -> list[dict]:
    store = DomainStore(session)
    rows = store.list_budget_categories(budget_id)
    return [BudgetCategoryView.model_validate(r).model_dump(mode="json") for r in rows]
