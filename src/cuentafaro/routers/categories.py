from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from cuentafaro.deps import get_session
from cuentafaro.schemas import (
    CategoryCreate,
    CategoryUpdate,
    CategoryView,
    IncomeSourceCreate,
    IncomeSourceUpdate,
    IncomeSourceView,
)
from cuentafaro.services import DomainStore

router = APIRouter(tags=["categories"])
SessionDependency = Annotated[Session, Depends(get_session)]


@router.post("/households/{household_id}/categories", response_model=CategoryView, status_code=201)
def create_category(household_id: str, payload: CategoryCreate, session: SessionDependency) -> dict:
    store = DomainStore(session)
    category = store.create_category(
        household_id, name=payload.name, kind=payload.kind, status=payload.status
    )
    return CategoryView.model_validate(category).model_dump(mode="json")


@router.get("/households/{household_id}/categories", response_model=list[CategoryView])
def list_categories(household_id: str, session: SessionDependency) -> list[dict]:
    store = DomainStore(session)
    categories = store.list_categories(household_id)
    return [CategoryView.model_validate(c).model_dump(mode="json") for c in categories]


@router.patch("/categories/{category_id}", response_model=CategoryView)
def update_category(category_id: str, payload: CategoryUpdate, session: SessionDependency) -> dict:
    store = DomainStore(session)
    category = store.update_category(
        category_id, name=payload.name, kind=payload.kind, status=payload.status
    )
    return CategoryView.model_validate(category).model_dump(mode="json")


@router.post(
    "/households/{household_id}/income-sources", response_model=IncomeSourceView, status_code=201
)
def create_income_source(
    household_id: str, payload: IncomeSourceCreate, session: SessionDependency
) -> dict:
    store = DomainStore(session)
    source = store.create_income_source(
        household_id,
        member_id=payload.member_id,
        name=payload.name,
        type=payload.type,
        expected_amount=payload.expected_amount,
        frequency=payload.frequency,
        status=payload.status,
    )
    return IncomeSourceView.model_validate(source).model_dump(mode="json")


@router.get("/households/{household_id}/income-sources", response_model=list[IncomeSourceView])
def list_income_sources(household_id: str, session: SessionDependency) -> list[dict]:
    store = DomainStore(session)
    sources = store.list_income_sources(household_id)
    return [IncomeSourceView.model_validate(s).model_dump(mode="json") for s in sources]


@router.patch("/income-sources/{source_id}", response_model=IncomeSourceView)
def update_income_source(
    source_id: str, payload: IncomeSourceUpdate, session: SessionDependency
) -> dict:
    store = DomainStore(session)
    source = store.update_income_source(
        source_id,
        member_id=payload.member_id,
        name=payload.name,
        type=payload.type,
        expected_amount=payload.expected_amount,
        frequency=payload.frequency,
        status=payload.status,
    )
    return IncomeSourceView.model_validate(source).model_dump(mode="json")


@router.delete("/income-sources/{source_id}", status_code=204)
def delete_income_source(source_id: str, session: SessionDependency) -> None:
    store = DomainStore(session)
    store.delete_income_source(source_id)
