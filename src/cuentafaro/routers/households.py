from typing import Annotated

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.orm import Session

from cuentafaro.deps import get_session
from cuentafaro.schemas import (
    HouseholdCreate,
    HouseholdUpdate,
    HouseholdView,
    MemberCreate,
    MemberUpdate,
    MemberView,
)
from cuentafaro.services import DomainStore

router = APIRouter(tags=["households"])
SessionDependency = Annotated[Session, Depends(get_session)]


@router.post("/households", response_model=HouseholdView, status_code=201)
def create_household(payload: HouseholdCreate, session: SessionDependency) -> dict:
    store = DomainStore(session)
    household = store.create_household(
        name=payload.name, timezone=payload.timezone, status=payload.status
    )
    return HouseholdView.model_validate(household).model_dump(mode="json")


@router.get("/households", response_model=list[HouseholdView])
def list_households(session: SessionDependency) -> list[dict]:
    store = DomainStore(session)
    return [
        HouseholdView.model_validate(h).model_dump(mode="json") for h in store.list_households()
    ]


@router.get("/households/{household_id}", response_model=HouseholdView)
def get_household(household_id: str, session: SessionDependency) -> dict:
    store = DomainStore(session)
    household = store.get_household(household_id)
    return HouseholdView.model_validate(household).model_dump(mode="json")


@router.patch("/households/{household_id}", response_model=HouseholdView)
def update_household(
    household_id: str, payload: HouseholdUpdate, session: SessionDependency
) -> dict:
    store = DomainStore(session)
    household = store.update_household(
        household_id,
        name=payload.name,
        timezone=payload.timezone,
        status=payload.status,
    )
    return HouseholdView.model_validate(household).model_dump(mode="json")


@router.delete("/households/{household_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_household(household_id: str, session: SessionDependency) -> Response:
    store = DomainStore(session)
    store.delete_household(household_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/households/{household_id}/members", response_model=MemberView, status_code=201)
def create_member(household_id: str, payload: MemberCreate, session: SessionDependency) -> dict:
    store = DomainStore(session)
    member = store.create_member(
        household_id, name=payload.name, role=payload.role, status=payload.status
    )
    return MemberView.model_validate(member).model_dump(mode="json")


@router.get("/households/{household_id}/members", response_model=list[MemberView])
def list_members(household_id: str, session: SessionDependency) -> list[dict]:
    store = DomainStore(session)
    members = store.list_members(household_id)
    return [MemberView.model_validate(m).model_dump(mode="json") for m in members]


@router.get("/members/{member_id}", response_model=MemberView)
def get_member(member_id: str, session: SessionDependency) -> dict:
    store = DomainStore(session)
    member = store.get_member(member_id)
    return MemberView.model_validate(member).model_dump(mode="json")


@router.delete("/members/{member_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_member(member_id: str, session: SessionDependency) -> Response:
    store = DomainStore(session)
    store.delete_member(member_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.patch("/members/{member_id}", response_model=MemberView)
def update_member(member_id: str, payload: MemberUpdate, session: SessionDependency) -> dict:
    store = DomainStore(session)
    member = store.update_member(
        member_id, name=payload.name, role=payload.role, status=payload.status
    )
    return MemberView.model_validate(member).model_dump(mode="json")
