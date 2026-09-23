from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from cuentafaro.deps import get_session
from cuentafaro.schemas import (
    DebtCreate,
    DebtPaymentCreate,
    DebtPaymentView,
    DebtUpdate,
    DebtView,
    InstallmentCreate,
    InstallmentUpdate,
    InstallmentView,
)
from cuentafaro.services import DomainStore

router = APIRouter(tags=["debts"])
SessionDependency = Annotated[Session, Depends(get_session)]


@router.post("/households/{household_id}/debts", response_model=DebtView, status_code=201)
def create_debt(household_id: str, payload: DebtCreate, session: SessionDependency) -> dict:
    store = DomainStore(session)
    debt = store.create_debt(
        household_id,
        account_id=payload.account_id,
        name=payload.name,
        type=payload.type,
        original_amount=payload.original_amount,
        minimum_payment=payload.minimum_payment,
        interest_rate=payload.interest_rate,
        due_day=payload.due_day,
        status=payload.status,
    )
    return DebtView.model_validate(debt).model_dump(mode="json")


@router.get("/households/{household_id}/debts", response_model=list[DebtView])
def list_debts(household_id: str, session: SessionDependency) -> list[dict]:
    store = DomainStore(session)
    debts = store.list_debts(household_id)
    return [DebtView.model_validate(d).model_dump(mode="json") for d in debts]


@router.get("/debts/{debt_id}", response_model=DebtView)
def get_debt(debt_id: str, session: SessionDependency) -> dict:
    store = DomainStore(session)
    debt = store.get_debt(debt_id)
    return DebtView.model_validate(debt).model_dump(mode="json")


@router.patch("/debts/{debt_id}", response_model=DebtView)
def update_debt(debt_id: str, payload: DebtUpdate, session: SessionDependency) -> dict:
    store = DomainStore(session)
    debt = store.update_debt(
        debt_id,
        account_id=payload.account_id,
        name=payload.name,
        type=payload.type,
        current_balance=payload.current_balance,
        minimum_payment=payload.minimum_payment,
        interest_rate=payload.interest_rate,
        due_day=payload.due_day,
        status=payload.status,
    )
    return DebtView.model_validate(debt).model_dump(mode="json")


@router.post("/debts/{debt_id}/payments", response_model=DebtPaymentView, status_code=201)
def pay_debt(debt_id: str, payload: DebtPaymentCreate, session: SessionDependency) -> dict:
    store = DomainStore(session)
    payment = store.pay_debt(
        debt_id,
        account_id=payload.account_id,
        recorded_by=payload.recorded_by,
        amount=payload.amount,
        type=payload.type,
        payment_date=payload.payment_date,
    )
    return DebtPaymentView.model_validate(payment).model_dump(mode="json")


@router.get("/debts/{debt_id}/payments", response_model=list[DebtPaymentView])
def list_debt_payments(debt_id: str, session: SessionDependency) -> list[dict]:
    store = DomainStore(session)
    payments = store.list_debt_payments(debt_id)
    return [DebtPaymentView.model_validate(p).model_dump(mode="json") for p in payments]


@router.post("/debts/{debt_id}/installments", response_model=InstallmentView, status_code=201)
def create_installment(
    debt_id: str, payload: InstallmentCreate, session: SessionDependency
) -> dict:
    store = DomainStore(session)
    installment = store.create_installment(
        debt_id,
        due_date=payload.due_date,
        principal_amount=payload.principal_amount,
        interest_amount=payload.interest_amount,
        fee_amount=payload.fee_amount,
    )
    return InstallmentView.model_validate(installment).model_dump(mode="json")


@router.get("/debts/{debt_id}/installments", response_model=list[InstallmentView])
def list_installments(debt_id: str, session: SessionDependency) -> list[dict]:
    store = DomainStore(session)
    installments = store.list_installments(debt_id)
    return [InstallmentView.model_validate(i).model_dump(mode="json") for i in installments]


@router.patch("/installments/{installment_id}", response_model=InstallmentView)
def update_installment(
    installment_id: str, payload: InstallmentUpdate, session: SessionDependency
) -> dict:
    store = DomainStore(session)
    installment = store.update_installment(installment_id, status=payload.status)
    return InstallmentView.model_validate(installment).model_dump(mode="json")
