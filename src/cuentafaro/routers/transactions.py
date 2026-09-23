from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from cuentafaro.deps import get_session
from cuentafaro.schemas import TransactionCreate, TransactionUpdate, TransactionView
from cuentafaro.services import DomainStore

router = APIRouter(tags=["transactions"])
SessionDependency = Annotated[Session, Depends(get_session)]


@router.post("/transactions", response_model=TransactionView, status_code=201)
def create_transaction(payload: TransactionCreate, session: SessionDependency) -> dict:
    store = DomainStore(session)
    transaction = store.create_transaction(
        account_id=payload.account_id,
        to_account_id=payload.to_account_id,
        category_id=payload.category_id,
        recorded_by=payload.recorded_by,
        type=payload.type,
        amount=payload.amount,
        date=payload.date,
        description=payload.description,
    )
    return TransactionView.model_validate(transaction).model_dump(mode="json")


@router.get("/transactions", response_model=list[TransactionView])
def list_transactions(
    session: SessionDependency,
    household_id: str | None = Query(default=None),
    account_id: str | None = Query(default=None),
    year: int | None = Query(default=None, ge=2000, le=2100),
    month: int | None = Query(default=None, ge=1, le=12),
    q: str | None = Query(default=None, max_length=200),
) -> list[dict]:
    store = DomainStore(session)
    transactions = store.list_transactions(
        household_id=household_id,
        account_id=account_id,
        year=year,
        month=month,
        q=q,
    )
    return [TransactionView.model_validate(t).model_dump(mode="json") for t in transactions]


@router.get("/transactions/{transaction_id}", response_model=TransactionView)
def get_transaction(transaction_id: str, session: SessionDependency) -> dict:
    store = DomainStore(session)
    transaction = store.get_transaction(transaction_id)
    return TransactionView.model_validate(transaction).model_dump(mode="json")


@router.post("/transactions/{transaction_id}/void", response_model=TransactionView)
def void_transaction(transaction_id: str, session: SessionDependency) -> dict:
    store = DomainStore(session)
    transaction = store.void_transaction(transaction_id)
    return TransactionView.model_validate(transaction).model_dump(mode="json")


@router.patch("/transactions/{transaction_id}", response_model=TransactionView)
def update_transaction(
    transaction_id: str, payload: TransactionUpdate, session: SessionDependency
) -> dict:
    store = DomainStore(session)
    transaction = store.update_transaction(
        transaction_id,
        account_id=payload.account_id,
        to_account_id=payload.to_account_id,
        category_id=payload.category_id,
        type=payload.type,
        amount=payload.amount,
        date=payload.date,
        description=payload.description,
    )
    return TransactionView.model_validate(transaction).model_dump(mode="json")
