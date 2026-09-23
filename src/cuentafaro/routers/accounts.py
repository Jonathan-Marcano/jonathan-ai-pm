from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from cuentafaro.deps import get_session
from cuentafaro.schemas import (
    AccountCreate,
    AccountUpdate,
    AccountView,
    InstitutionCreate,
    InstitutionUpdate,
    InstitutionView,
)
from cuentafaro.services import DomainStore

router = APIRouter(tags=["accounts"])
SessionDependency = Annotated[Session, Depends(get_session)]


def _account_view(store: DomainStore, account, institutions: dict[str, str] | None = None) -> dict:
    data = AccountView.model_validate(account).model_dump(mode="json")
    if account.institution_id:
        data["institution_name"] = (
            institutions.get(account.institution_id)
            if institutions is not None
            else store.institution_name(account.institution_id)
        )
    else:
        data["institution_name"] = None
    return data


@router.post("/financial-institutions", response_model=InstitutionView, status_code=201)
def create_institution(payload: InstitutionCreate, session: SessionDependency) -> dict:
    store = DomainStore(session)
    institution = store.create_institution(
        name=payload.name, type=payload.type, status=payload.status
    )
    return InstitutionView.model_validate(institution).model_dump(mode="json")


@router.get("/financial-institutions", response_model=list[InstitutionView])
def list_institutions(session: SessionDependency) -> list[dict]:
    store = DomainStore(session)
    return [
        InstitutionView.model_validate(i).model_dump(mode="json") for i in store.list_institutions()
    ]


@router.patch("/financial-institutions/{institution_id}", response_model=InstitutionView)
def update_institution(
    institution_id: str, payload: InstitutionUpdate, session: SessionDependency
) -> dict:
    store = DomainStore(session)
    institution = store.update_institution(
        institution_id, name=payload.name, type=payload.type, status=payload.status
    )
    return InstitutionView.model_validate(institution).model_dump(mode="json")


@router.delete("/financial-institutions/{institution_id}", status_code=204)
def delete_institution(institution_id: str, session: SessionDependency) -> None:
    store = DomainStore(session)
    store.delete_institution(institution_id)


@router.post("/accounts", response_model=AccountView, status_code=201)
def create_account(payload: AccountCreate, session: SessionDependency) -> dict:
    store = DomainStore(session)
    account = store.create_account(
        household_id=payload.household_id,
        institution_id=payload.institution_id,
        name=payload.name,
        type=payload.type,
        currency=payload.currency,
        balance_reported=payload.balance_reported,
        balance_calculated=payload.balance_calculated or payload.balance_reported,
        original_amount=payload.original_amount,
        credit_limit=payload.credit_limit,
        statement_day=payload.statement_day,
        due_day=payload.due_day,
        status=payload.status,
    )
    return _account_view(store, account)


@router.get("/accounts", response_model=list[AccountView])
def list_accounts(
    session: SessionDependency, household_id: str | None = Query(default=None)
) -> list[dict]:
    store = DomainStore(session)
    accounts = store.list_accounts(household_id)
    institutions = {i.id: i.name for i in store.list_institutions()}
    return [_account_view(store, a, institutions) for a in accounts]


@router.get("/accounts/{account_id}", response_model=AccountView)
def get_account(account_id: str, session: SessionDependency) -> dict:
    store = DomainStore(session)
    account = store.get_account(account_id)
    return _account_view(store, account)


@router.patch("/accounts/{account_id}", response_model=AccountView)
def update_account(account_id: str, payload: AccountUpdate, session: SessionDependency) -> dict:
    store = DomainStore(session)
    account = store.update_account(
        account_id,
        institution_id=payload.institution_id,
        name=payload.name,
        type=payload.type,
        balance_reported=payload.balance_reported,
        credit_limit=payload.credit_limit,
        statement_day=payload.statement_day,
        due_day=payload.due_day,
        status=payload.status,
    )
    return _account_view(store, account)
