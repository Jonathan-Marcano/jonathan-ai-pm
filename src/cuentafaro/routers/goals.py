from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from cuentafaro.deps import get_session
from cuentafaro.schemas import GoalContribute, GoalCreate, GoalUpdate, GoalView
from cuentafaro.services import DomainStore

router = APIRouter(tags=["goals"])
SessionDependency = Annotated[Session, Depends(get_session)]


@router.post(
    "/households/{household_id}/goals",
    response_model=GoalView,
    status_code=status.HTTP_201_CREATED,
)
def create_goal(household_id: str, payload: GoalCreate, session: SessionDependency) -> dict:
    store = DomainStore(session)
    goal = store.create_goal(
        household_id,
        name=payload.name,
        category=payload.category,
        target_amount=payload.target_amount,
        current_amount=payload.current_amount,
        monthly_contribution=payload.monthly_contribution,
        target_date=payload.target_date,
        status=payload.status,
    )
    return GoalView.model_validate(goal).model_dump(mode="json")


@router.get("/households/{household_id}/goals", response_model=list[GoalView])
def list_goals(household_id: str, session: SessionDependency) -> list[dict]:
    store = DomainStore(session)
    goals = store.list_goals(household_id)
    return [GoalView.model_validate(g).model_dump(mode="json") for g in goals]


@router.get("/goals/{goal_id}", response_model=GoalView)
def get_goal(goal_id: str, session: SessionDependency) -> dict:
    store = DomainStore(session)
    goal = store.get_goal(goal_id)
    return GoalView.model_validate(goal).model_dump(mode="json")


@router.patch("/goals/{goal_id}", response_model=GoalView)
def update_goal(goal_id: str, payload: GoalUpdate, session: SessionDependency) -> dict:
    store = DomainStore(session)
    goal = store.update_goal(
        goal_id,
        name=payload.name,
        category=payload.category,
        target_amount=payload.target_amount,
        current_amount=payload.current_amount,
        monthly_contribution=payload.monthly_contribution,
        target_date=payload.target_date,
        status=payload.status,
    )
    return GoalView.model_validate(goal).model_dump(mode="json")


@router.post("/goals/{goal_id}/contributions", response_model=GoalView)
def contribute_goal(goal_id: str, payload: GoalContribute, session: SessionDependency) -> dict:
    store = DomainStore(session)
    goal = store.contribute_goal(goal_id, amount=payload.amount)
    return GoalView.model_validate(goal).model_dump(mode="json")


@router.delete("/goals/{goal_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_goal(goal_id: str, session: SessionDependency) -> None:
    store = DomainStore(session)
    store.delete_goal(goal_id)