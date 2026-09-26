from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from cuentafaro.audit import ACTOR_KEY
from cuentafaro.db import get_session_factory
from cuentafaro.deps import get_session as get_finance_session
from faroflow.models import BandejaItem, Habit
from faroflow.schemas import (
    BandejaApply,
    BandejaItemRead,
    BandejaItemUpdate,
    BandejaKind,
    BandejaReceive,
    BandejaStatus,
    HabitCompletionRead,
    HabitCreate,
    HabitMark,
    HabitRead,
    HabitSeriesRead,
    HabitUndo,
    HabitUpdate,
    HomeData,
)
from faroflow.services import DomainRuleError, DomainStore
from faroflow.unified import HabitService, HomeService, InboxService

from .deps import DbSession, PageLimit, PageOffset, domain_http_error

router = APIRouter()
FinanceSession = Annotated[Session, Depends(get_finance_session)]


def _optional_finance_session(request: Request):
    """Finance session dependency that tolerates an unconfigured finance datastore."""
    try:
        session = get_session_factory()()
    except Exception:
        yield None
        return
    session.info[ACTOR_KEY] = (request.headers.get("X-Actor") or "").strip() or None
    try:
        yield session
    finally:
        session.close()


OptionalFinanceSession = Annotated[Session | None, Depends(_optional_finance_session)]


def _habit(session: DbSession, habit_id: str) -> Habit:
    habit = session.get(Habit, habit_id)
    if habit is None:
        raise HTTPException(status_code=404, detail="habit not found")
    return habit


def _item(session: DbSession, item_id: str) -> BandejaItem:
    item = session.get(BandejaItem, item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="bandeja item not found")
    return item


# ---------- Hábitos ----------


@router.post("/api/v1/habits", response_model=HabitRead, status_code=201, tags=["habits"])
def create_habit(payload: HabitCreate, session: DbSession):
    try:
        return DomainStore(session).create("habit", **payload.model_dump())
    except DomainRuleError as exc:
        session.rollback()
        raise domain_http_error(exc) from exc


@router.get("/api/v1/habits", response_model=list[HabitRead], tags=["habits"])
def list_habits(
    session: DbSession,
    habit_status: Annotated[str | None, Query(alias="status")] = None,
    limit: PageLimit = None,
    offset: PageOffset = 0,
):
    items, _has_more = DomainStore(session).list_page(
        "habit", limit=limit, offset=offset, status=habit_status
    )
    return items


@router.get("/api/v1/habits/{habit_id}", response_model=HabitRead, tags=["habits"])
def get_habit(habit_id: str, session: DbSession):
    return _habit(session, habit_id)


@router.patch("/api/v1/habits/{habit_id}", response_model=HabitRead, tags=["habits"])
def update_habit(habit_id: str, payload: HabitUpdate, session: DbSession):
    try:
        return DomainStore(session).update(
            "habit", habit_id, **payload.model_dump(exclude_unset=True)
        )
    except DomainRuleError as exc:
        session.rollback()
        raise domain_http_error(exc) from exc


@router.delete("/api/v1/habits/{habit_id}", status_code=204, tags=["habits"])
def delete_habit(habit_id: str, session: DbSession):
    try:
        DomainStore(session).delete("habit", habit_id)
    except DomainRuleError as exc:
        session.rollback()
        raise domain_http_error(exc) from exc
    return Response(status_code=204)


@router.get(
    "/api/v1/habits/{habit_id}/series", response_model=HabitSeriesRead, tags=["habits"]
)
def habit_series(habit_id: str, session: DbSession):
    return HabitService(session).series(_habit(session, habit_id))


@router.post(
    "/api/v1/habits/{habit_id}/mark",
    response_model=HabitCompletionRead,
    status_code=201,
    tags=["habits"],
)
def mark_habit(habit_id: str, payload: HabitMark, session: DbSession):
    try:
        return HabitService(session).mark(
            _habit(session, habit_id),
            local_date=payload.local_date,
            quantity=payload.quantity,
            note=payload.note,
            source=payload.source,
            external_ref=payload.external_ref,
        )
    except DomainRuleError as exc:
        session.rollback()
        raise domain_http_error(exc) from exc


@router.post(
    "/api/v1/habits/{habit_id}/unmark", response_model=HabitSeriesRead, tags=["habits"]
)
def unmark_habit(habit_id: str, payload: HabitUndo, session: DbSession):
    habit = _habit(session, habit_id)
    HabitService(session).unmark(habit, local_date=payload.local_date)
    return HabitService(session).series(habit)


# ---------- Bandeja ----------


@router.post(
    "/api/v1/bandeja", response_model=BandejaItemRead, status_code=201, tags=["bandeja"]
)
def receive_bandeja(payload: BandejaReceive, session: DbSession):
    try:
        return InboxService(session).receive(
            channel=payload.channel,
            author=payload.author,
            source_ref=payload.source_ref,
            original_text=payload.original_text,
            original_at=payload.original_at,
            kind=payload.kind,
            amount=payload.amount,
            attachments=[a.model_dump() for a in payload.attachments],
            drive_file_id=payload.drive_file_id,
            drive_version=payload.drive_version,
        )
    except DomainRuleError as exc:
        session.rollback()
        raise domain_http_error(exc) from exc


@router.get("/api/v1/bandeja", response_model=list[BandejaItemRead], tags=["bandeja"])
def list_bandeja(
    session: DbSession,
    b_status: Annotated[BandejaStatus | None, Query(alias="status")] = None,
    kind: BandejaKind | None = None,
    channel: str | None = None,
    limit: PageLimit = None,
    offset: PageOffset = 0,
):
    from sqlalchemy import select

    statement = select(BandejaItem)
    if b_status:
        statement = statement.where(BandejaItem.status == b_status)
    if kind:
        statement = statement.where(BandejaItem.kind == kind)
    if channel:
        statement = statement.where(BandejaItem.channel == channel)
    statement = statement.order_by(BandejaItem.original_at.desc(), BandejaItem.id).offset(offset)
    if limit is None:
        return list(session.scalars(statement))
    return list(session.scalars(statement.limit(limit)))


@router.get("/api/v1/bandeja/{item_id}", response_model=BandejaItemRead, tags=["bandeja"])
def get_bandeja(item_id: str, session: DbSession):
    return _item(session, item_id)


@router.patch("/api/v1/bandeja/{item_id}", response_model=BandejaItemRead, tags=["bandeja"])
def refine_bandeja(item_id: str, payload: BandejaItemUpdate, session: DbSession):
    try:
        return InboxService(session).refine(item_id, **payload.model_dump(exclude_unset=True))
    except DomainRuleError as exc:
        session.rollback()
        raise domain_http_error(exc) from exc


@router.delete(
    "/api/v1/bandeja/{item_id}", status_code=status.HTTP_204_NO_CONTENT, tags=["bandeja"]
)
def delete_bandeja(item_id: str, session: DbSession):
    try:
        InboxService(session).delete(item_id)
    except DomainRuleError as exc:
        session.rollback()
        raise domain_http_error(exc) from exc


class BandejaDiscard(BaseModel):
    note: str | None = None


@router.post(
    "/api/v1/bandeja/{item_id}/discard", response_model=BandejaItemRead, tags=["bandeja"]
)
def discard_bandeja(item_id: str, payload: BandejaDiscard, session: DbSession):
    try:
        return InboxService(session).discard(item_id, note=payload.note)
    except DomainRuleError as exc:
        session.rollback()
        raise domain_http_error(exc) from exc


@router.post(
    "/api/v1/bandeja/{item_id}/apply", response_model=BandejaItemRead, tags=["bandeja"]
)
def apply_bandeja(
    item_id: str,
    payload: BandejaApply,
    work_session: DbSession,
    finance_session: FinanceSession,
):
    try:
        return InboxService(work_session).apply(
            item_id,
            decision=payload.decision,
            payload=payload.model_dump(exclude_unset=True),
            work_session=work_session,
            finance_session=finance_session,
        )
    except DomainRuleError as exc:
        work_session.rollback()
        raise domain_http_error(exc) from exc


# ---------- Mi día ----------


@router.get("/api/v1/home", response_model=HomeData, tags=["home"])
def unified_home(work_session: DbSession, finance_session: OptionalFinanceSession):
    try:
        return HomeService(work_session, finance_session).build()
    except DomainRuleError as exc:
        work_session.rollback()
        raise domain_http_error(exc) from exc