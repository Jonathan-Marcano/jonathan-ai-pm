from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from cuentafaro.deps import get_session
from cuentafaro.schemas import (
    PaymentPlanCreate,
    PaymentPlanUpdate,
    PaymentPlanView,
    ProjectionScenarioView,
    ScenarioCreate,
    StrategySimulationRequest,
)
from cuentafaro.services import DomainStore

router = APIRouter(tags=["projections"])
SessionDependency = Annotated[Session, Depends(get_session)]


@router.post("/households/{household_id}/projections/simulate")
def simulate_strategy(
    household_id: str, payload: StrategySimulationRequest, session: SessionDependency
) -> dict:
    store = DomainStore(session)
    return store.simulate_strategy(
        household_id, strategy=payload.strategy, monthly_payment=payload.monthly_payment
    )


@router.post("/households/{household_id}/plans", response_model=PaymentPlanView, status_code=201)
def create_payment_plan(
    household_id: str, payload: PaymentPlanCreate, session: SessionDependency
) -> dict:
    store = DomainStore(session)
    plan = store.create_payment_plan(household_id, strategy=payload.strategy, name=payload.name)
    return PaymentPlanView.model_validate(plan).model_dump(mode="json")


@router.get("/households/{household_id}/plans", response_model=list[PaymentPlanView])
def list_payment_plans(household_id: str, session: SessionDependency) -> list[dict]:
    store = DomainStore(session)
    plans = store.list_payment_plans(household_id)
    return [PaymentPlanView.model_validate(p).model_dump(mode="json") for p in plans]


@router.get("/plans/{plan_id}", response_model=PaymentPlanView)
def get_payment_plan(plan_id: str, session: SessionDependency) -> dict:
    store = DomainStore(session)
    plan = store.get_payment_plan(plan_id)
    return PaymentPlanView.model_validate(plan).model_dump(mode="json")


@router.patch("/plans/{plan_id}", response_model=PaymentPlanView)
def update_payment_plan(
    plan_id: str, payload: PaymentPlanUpdate, session: SessionDependency
) -> dict:
    store = DomainStore(session)
    plan = store.update_payment_plan(plan_id, status=payload.status)
    return PaymentPlanView.model_validate(plan).model_dump(mode="json")


@router.post("/plans/{plan_id}/scenarios", response_model=ProjectionScenarioView, status_code=201)
def run_scenario(plan_id: str, payload: ScenarioCreate, session: SessionDependency) -> dict:
    store = DomainStore(session)
    scenario = store.run_scenario(
        plan_id,
        name=payload.name,
        monthly_payment=payload.monthly_payment,
        extra_income=[item.model_dump() for item in payload.extra_income],
    )
    return ProjectionScenarioView.model_validate(scenario).model_dump(mode="json")


@router.get("/plans/{plan_id}/scenarios", response_model=list[ProjectionScenarioView])
def list_scenarios(plan_id: str, session: SessionDependency) -> list[dict]:
    store = DomainStore(session)
    scenarios = store.list_scenarios(plan_id)
    return [ProjectionScenarioView.model_validate(s).model_dump(mode="json") for s in scenarios]


@router.get("/scenarios/{scenario_id}", response_model=ProjectionScenarioView)
def get_scenario(scenario_id: str, session: SessionDependency) -> dict:
    store = DomainStore(session)
    scenario = store.get_scenario(scenario_id)
    return ProjectionScenarioView.model_validate(scenario).model_dump(mode="json")
