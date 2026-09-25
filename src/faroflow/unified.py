from __future__ import annotations

from datetime import UTC, date, datetime, time, timedelta
from typing import Any
from uuid import uuid4
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy import select
from sqlalchemy.orm import Session

from cuentafaro.services import DomainStore as FinanceDomainStore
from faroflow.config import get_settings
from faroflow.models import (
    BandejaItem,
    Habit,
    HabitCompletion,
    Meeting,
    Project,
    Task,
    utc_now,
)
from faroflow.services import DomainRuleError, DomainStore


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex[:12]}"


def _safe_zone(name: str) -> ZoneInfo:
    try:
        return ZoneInfo(name)
    except (ZoneInfoNotFoundError, ValueError):
        return ZoneInfo("UTC")


class HabitService:
    def __init__(self, session: Session):
        self.session = session

    def today(self, habit: Habit) -> date:
        return datetime.now(_safe_zone(habit.timezone)).date()

    @staticmethod
    def is_scheduled(habit: Habit, day: date) -> bool:
        if habit.frequency == "weekdays":
            return day.isoweekday() <= 5
        if habit.frequency == "specific_days":
            return day.isoweekday() in (habit.specific_days or [])
        return True

    @staticmethod
    def week_start(day: date) -> date:
        return day - timedelta(days=day.isoweekday() - 1)

    def is_met(self, habit: Habit, day: date, quantities_by_day: dict[date, int]) -> bool:
        if habit.frequency == "weekly":
            ws = self.week_start(day)
            total = sum(
                q
                for d, q in quantities_by_day.items()
                if ws <= d <= ws + timedelta(days=6)
            )
            return total >= (habit.weekly_target or 1)
        total = quantities_by_day.get(day, 0)
        if habit.goal_type == "binary":
            return total >= 1
        return total >= habit.target_quantity

    def quantities_by_date(self, habit_id: str, start: date, end: date) -> dict[date, int]:
        rows = self.session.scalars(
            select(HabitCompletion).where(
                HabitCompletion.habit_id == habit_id,
                HabitCompletion.local_date.between(start, end),
            )
        )
        out: dict[date, int] = {}
        for row in rows:
            out[row.local_date] = out.get(row.local_date, 0) + row.quantity
        return out

    def completions(self, habit_id: str, limit: int = 120) -> list[HabitCompletion]:
        statement = (
            select(HabitCompletion)
            .where(HabitCompletion.habit_id == habit_id)
            .order_by(HabitCompletion.local_date.desc(), HabitCompletion.id)
            .limit(limit)
        )
        return list(self.session.scalars(statement))

    def mark(
        self,
        habit: Habit,
        *,
        local_date: date | None = None,
        quantity: int = 1,
        note: str | None = None,
        source: str = "manual",
        external_ref: str | None = None,
    ) -> HabitCompletion:
        if habit.status == "archived":
            raise DomainRuleError("Archived habits cannot record completions")
        if source in ("telegram", "bandeja") and not external_ref:
            raise DomainRuleError("External sources require an external_ref for deduplication")
        if quantity < 1:
            raise DomainRuleError("A completion requires quantity >= 1")
        if habit.goal_type == "binary" and quantity != 1:
            raise DomainRuleError("Binary habits only accept a quantity of 1")
        target_date = local_date or self.today(habit)

        if external_ref:
            existing = self.session.scalar(
                select(HabitCompletion).where(
                    HabitCompletion.habit_id == habit.id,
                    HabitCompletion.external_ref == external_ref,
                )
            )
            if existing is not None:
                existing.updated_at = utc_now()
                self.session.commit()
                self.session.refresh(existing)
                return existing
            if habit.goal_type == "binary":
                same_day = self.session.scalar(
                    select(HabitCompletion).where(
                        HabitCompletion.habit_id == habit.id,
                        HabitCompletion.local_date == target_date,
                    )
                )
                if same_day is not None:
                    return same_day
            row = HabitCompletion(
                id=new_id("hcp"),
                habit_id=habit.id,
                local_date=target_date,
                quantity=quantity,
                note=note,
                source=source,
                external_ref=external_ref,
            )
            self.session.add(row)
            self.session.commit()
            self.session.refresh(row)
            return row

        row = self.session.scalar(
            select(HabitCompletion).where(
                HabitCompletion.habit_id == habit.id,
                HabitCompletion.local_date == target_date,
            )
        )
        if row is not None:
            if habit.goal_type == "binary":
                row.updated_at = utc_now()
                self.session.commit()
                self.session.refresh(row)
                return row
            row.quantity += quantity
            if note:
                row.note = note
            self.session.commit()
            self.session.refresh(row)
            return row

        row = HabitCompletion(
            id=new_id("hcp"),
            habit_id=habit.id,
            local_date=target_date,
            quantity=quantity,
            note=note,
            source=source,
        )
        self.session.add(row)
        self.session.commit()
        self.session.refresh(row)
        return row

    def unmark(self, habit: Habit, *, local_date: date | None = None) -> bool:
        target_date = local_date or self.today(habit)
        rows = self.session.scalars(
            select(HabitCompletion).where(
                HabitCompletion.habit_id == habit.id,
                HabitCompletion.local_date == target_date,
            )
        )
        found = False
        for row in list(rows):
            self.session.delete(row)
            found = True
        if found:
            self.session.commit()
        return found

    def week_summary(
        self,
        habit: Habit,
        quantities: dict[date, int],
        today: date,
    ) -> dict[str, Any]:
        """Resumen de la semana natural (lunes a domingo) que contiene `today`.

        Solo se contabilizan los días ya transcurridos: un día futuro nunca
        cuenta como incumplimiento. Los hábitos `weekly` no se fijan en un día
        concreto, así que su cumplimiento se resuelve a nivel de semana
        (`goal_met`).
        """
        start = self.week_start(today)
        end = start + timedelta(days=6)
        goal_met = self.is_met(habit, today, quantities)
        is_weekly = habit.frequency == "weekly"

        days: list[dict[str, Any]] = []
        scheduled_days = 0
        met_days = 0
        total_quantity = 0
        walk = start
        while walk <= end:
            elapsed = walk <= today
            scheduled = self.is_scheduled(habit, walk)
            quantity = quantities.get(walk, 0)
            if is_weekly:
                met = False
                due = elapsed and not goal_met
            else:
                met = scheduled and self.is_met(habit, walk, quantities)
                due = scheduled and elapsed
            if elapsed:
                if is_weekly or scheduled:
                    scheduled_days += 1
                if met:
                    met_days += 1
                total_quantity += quantity
            days.append(
                {
                    "date": walk,
                    "scheduled": scheduled,
                    "due": due,
                    "met": met,
                    "quantity": quantity,
                    "is_today": walk == today,
                    "is_future": walk > today,
                }
            )
            walk += timedelta(days=1)

        return {
            "start": start,
            "end": end,
            "days": days,
            "scheduled_days": scheduled_days,
            "met_days": met_days,
            "total_quantity": total_quantity,
            "goal_met": goal_met,
            "rate": round(met_days / scheduled_days, 2) if scheduled_days else 0.0,
        }

    def series(self, habit: Habit) -> dict[str, Any]:
        today = self.today(habit)
        zone_name = habit.timezone
        window_start = today - timedelta(days=730)
        quantities = self.quantities_by_date(habit.id, window_start, today)
        completions = self.completions(habit.id)

        current_streak, longest_streak = self._streaks(habit, quantities, today)

        rate_days = 0
        rate_met = 0
        walk = today - timedelta(days=13)
        while walk <= today:
            if self.is_scheduled(habit, walk):
                rate_days += 1
                if self.is_met(habit, walk, quantities):
                    rate_met += 1
            walk += timedelta(days=1)
        rate = round((rate_met / rate_days) if rate_days else 0.0, 2)

        completed_today = self.is_met(habit, today, quantities)
        today_quantity = quantities.get(today, 0)

        return {
            "habit": habit,
            "today": today,
            "zone": zone_name,
            "completed_today": completed_today,
            "today_quantity": today_quantity,
            "current_streak": current_streak,
            "longest_streak": longest_streak,
            "completion_rate_14d": rate,
            "week": self.week_summary(habit, quantities, today),
            "completions": completions,
        }

    def _streaks(
        self,
        habit: Habit,
        quantities: dict[date, int],
        today: date,
    ) -> tuple[int, int]:
        if habit.frequency == "weekly":
            return self._weekly_streaks(habit, quantities, today)
        return self._daily_streaks(habit, quantities, today)

    def _daily_streaks(
        self, habit: Habit, quantities: dict[date, int], today: date
    ) -> tuple[int, int]:
        start = today - timedelta(days=730)
        met_days = [
            day
            for day in self._date_range(start, today)
            if self.is_scheduled(habit, day) and self.is_met(habit, day, quantities)
        ]
        longest = 0
        current = 0
        previous: date | None = None
        for day in met_days:
            if previous is not None and day == previous + timedelta(days=1):
                current += 1
            else:
                current = 1
            if current > longest:
                longest = current
            previous = day

        anchor = today
        if not (self.is_scheduled(habit, today) and self.is_met(habit, today, quantities)):
            anchor = today - timedelta(days=1)
        walk = anchor
        count = 0
        guard = 0
        while (
            guard < 750
            and self.is_scheduled(habit, walk)
            and self.is_met(habit, walk, quantities)
        ):
            count += 1
            walk -= timedelta(days=1)
            guard += 1
        return count, longest

    def _weekly_streaks(
        self, habit: Habit, quantities: dict[date, int], today: date
    ) -> tuple[int, int]:
        met_weeks: list[date] = []
        walk = self.week_start(today) - timedelta(days=730)
        end = self.week_start(today)
        while walk <= end:
            if self.is_met(habit, walk, quantities):
                met_weeks.append(walk)
            walk += timedelta(days=7)

        longest = 0
        current = 0
        previous: date | None = None
        for week in met_weeks:
            if previous is not None and week == previous + timedelta(days=7):
                current += 1
            else:
                current = 1
            if current > longest:
                longest = current
            previous = week

        this_week = self.week_start(today)
        if self.is_met(habit, this_week, quantities):
            anchor = this_week
        else:
            anchor = this_week - timedelta(days=7)
        count = 0
        walk = anchor
        guard = 0
        while guard < 120 and self.is_met(habit, walk, quantities):
            count += 1
            walk -= timedelta(days=7)
            guard += 1
        return count, longest

    @staticmethod
    def _date_range(start: date, end: date):
        day = start
        while day <= end:
            yield day
            day += timedelta(days=1)


class InboxService:
    def __init__(self, session: Session):
        self.session = session

    def _item(self, item_id: str) -> BandejaItem:
        item = self.session.get(BandejaItem, item_id)
        if item is None:
            raise DomainRuleError(f"Bandeja item not found: {item_id}")
        return item

    def receive(
        self,
        *,
        channel: str,
        source_ref: str,
        original_text: str,
        author: str | None = None,
        original_at: datetime | None = None,
        kind: str = "unknown",
        amount: int | None = None,
        attachments: list[dict] | None = None,
        drive_file_id: str | None = None,
        drive_version: str | None = None,
    ) -> BandejaItem:
        existing = self.session.scalar(
            select(BandejaItem).where(
                BandejaItem.channel == channel,
                BandejaItem.source_ref == source_ref,
            )
        )
        if existing is not None:
            return existing
        item = BandejaItem(
            id=new_id("bjx"),
            channel=channel,
            author=author,
            source_ref=source_ref,
            original_text=original_text,
            original_at=original_at or utc_now(),
            kind=kind,
            amount=amount,
            attachments=attachments or [],
            status="received",
            drive_file_id=drive_file_id,
            drive_version=drive_version,
        )
        self.session.add(item)
        self.session.commit()
        self.session.refresh(item)
        return item

    def refine(self, item_id: str, **changes: Any) -> BandejaItem:
        item = self._item(item_id)
        for name in (
            "kind",
            "amount",
            "account_id",
            "category_id",
            "project_id",
            "habit_id",
            "decision_note",
        ):
            if name in changes and changes[name] is not None:
                setattr(item, name, changes[name])
        if not changes.get("status"):
            item.status = "confirmed"
        self.session.commit()
        self.session.refresh(item)
        return item

    def discard(self, item_id: str, *, note: str | None = None) -> BandejaItem:
        item = self._item(item_id)
        item.status = "discarded"
        item.decision_note = note
        item.resolved_at = utc_now()
        self.session.commit()
        self.session.refresh(item)
        return item

    def apply(
        self,
        item_id: str,
        *,
        decision: str,
        payload: dict[str, Any],
        work_session: Session,
        finance_session: Session,
    ) -> BandejaItem:
        item = self._item(item_id)
        try:
            destination = self._execute_decision(
                decision, payload, item, work_session, finance_session
            )
        except Exception as exc:
            item.status = "error"
            item.error = str(exc)[:1000]
            item.attempts = item.attempts + 1
            self.session.commit()
            self.session.refresh(item)
            raise DomainRuleError(f"Routing failed: {exc}") from exc

        item.status = "applied"
        item.error = None
        item.destination_module = destination["module"]
        item.destination_ref = destination["ref"]
        item.decision_note = payload.get("note")
        item.resolved_at = utc_now()
        self.session.commit()
        self.session.refresh(item)
        return item

    def _execute_decision(
        self, decision: str, payload: dict[str, Any], item: BandejaItem,
        work_session: Session, finance_session: Session,
    ) -> dict[str, str]:
        if decision == "task":
            project_id = payload.get("project_id")
            if not project_id:
                raise DomainRuleError("A task decision requires project_id")
            work = DomainStore(work_session)
            task = work.create(
                "task",
                id=new_id("tsk"),
                project_id=project_id,
                title=item.original_text[:300],
                status="ready",
                priority=payload.get("priority", "medium"),
                due_at=payload.get("due_at"),
            )
            return {"module": "work", "ref": task.id}

        if decision in ("expense", "income"):
            return self._route_finance(decision, payload, item, finance_session)

        if decision == "habit":
            return self._route_habit(payload, item, work_session)

        if decision == "note":
            return {"module": "notes", "ref": ""}

        raise DomainRuleError(f"Unknown decision: {decision}")

    def _route_finance(
        self, decision: str, payload: dict[str, Any], item: BandejaItem,
        finance_session: Session,
    ) -> dict[str, str]:
        finance = FinanceDomainStore(finance_session)
        households = finance.list_households()
        if not households:
            raise DomainRuleError("No finance household has been configured yet")
        household = households[0]
        recorded_by = next(
            (m.id for m in finance.list_members(household.id) if m.name == item.author),
            None,
        )
        accounts = [a for a in finance.list_accounts(household.id) if a.status == "active"]
        if not accounts:
            raise DomainRuleError("No active finance account is available for this routing")
        account = next((a for a in accounts if a.id == payload.get("account_id")), accounts[0])

        amount = payload.get("amount") or item.amount
        if amount is None or int(amount) <= 0:
            raise DomainRuleError(f"{decision} routing requires a positive amount")
        try:
            from zoneinfo import ZoneInfo as TZ

            zone = TZ(household.timezone)
        except Exception:
            zone = ZoneInfo("UTC")
        recorded_on = payload.get("recorded_on") or datetime.now(zone).date()
        transaction = finance.create_transaction(
            account_id=account.id,
            to_account_id=None,
            category_id=payload.get("category_id"),
            recorded_by=recorded_by,
            type=decision,
            amount=int(amount),
            date=recorded_on,
            description=item.original_text[:500],
        )
        return {"module": "finance", "ref": transaction.id}

    def _route_habit(
        self, payload: dict[str, Any], item: BandejaItem, work_session: Session
    ) -> dict[str, str]:
        habit_id = payload.get("habit_id") or item.habit_id
        if not habit_id:
            raise DomainRuleError("A habit decision requires habit_id")
        habit = work_session.get(Habit, habit_id)
        if habit is None:
            raise DomainRuleError(f"Unknown habit: {habit_id}")
        service = HabitService(work_session)
        completion = service.mark(
            habit,
            local_date=_parse_date(payload.get("recorded_on")),
            quantity=int(payload.get("amount") or 1),
            source="bandeja",
            external_ref=f"bandeja:{item.id}",
        )
        return {"module": "habits", "ref": completion.id}


def _parse_date(value: Any) -> date | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError:
        return None


class HomeService:
    def __init__(self, work_session: Session, finance_session: Session | None):
        self.work = work_session
        self.finance = finance_session

    def build(self) -> dict[str, Any]:
        zone = _safe_zone(get_settings().app_timezone)
        today = datetime.now(zone).date()
        now = datetime.now(UTC)
        work = self._work_section(today)
        meetings = self._meetings_section(today, zone)
        projects = self._projects_section()
        bandeja = self._bandeja_section()
        habits = self._habits(today)
        finance = self._finance(today)
        return {
            "as_of": now,
            "timezone": str(zone),
            "date": today,
            "work": work,
            "meetings": meetings,
            "projects": projects,
            "bandeja": bandeja,
            "habits": habits,
            "finance": finance,
        }

    def _work_section(self, today: date) -> dict[str, Any]:
        rows = list(
            self.work.scalars(
                select(Task)
                .where(
                    Task.status.notin_(["done", "cancelled"]),
                    Task.due_at.is_not(None),
                    Task.due_at <= today,
                )
                .order_by(Task.due_at, Task.id)
            )
        )
        items = [
            {"id": t.id, "title": t.title, "status": t.status, "due_at": t.due_at}
            for t in rows
        ]
        return {"label": "tareas vencidas", "count": len(items), "items": items}

    def _meetings_section(self, today: date, zone: ZoneInfo) -> dict[str, Any]:
        start = datetime.combine(today, time.min, tzinfo=zone).astimezone(UTC)
        end = datetime.combine(today + timedelta(days=1), time.min, tzinfo=zone).astimezone(UTC)
        rows = list(
            self.work.scalars(
                select(Meeting)
                .where(
                    Meeting.status == "scheduled",
                    Meeting.starts_at >= start,
                    Meeting.starts_at < end,
                )
                .order_by(Meeting.starts_at, Meeting.id)
            )
        )
        items = [
            {"id": m.id, "title": m.title, "starts_at": m.starts_at, "project_id": m.project_id}
            for m in rows
        ]
        return {"label": "reuniones de hoy", "count": len(items), "items": items}

    def _projects_section(self) -> dict[str, Any]:
        rows = list(
            self.work.scalars(
                select(Project).where(Project.status.in_(["planned", "active", "paused"]))
            )
        )
        at_risk = [p for p in rows if p.health in ("at_risk", "off_track")]
        items = [
            {"id": p.id, "title": p.name, "status": p.status, "health": p.health}
            for p in at_risk
        ]
        return {"label": "proyectos en riesgo", "count": len(items), "items": items}

    def _bandeja_section(self) -> dict[str, Any]:
        rows = list(
            self.work.scalars(
                select(BandejaItem).where(
                    BandejaItem.status.in_(["received", "reviewing", "confirmed"]),
                )
            )
        )
        items = [
            {
                "id": r.id,
                "title": r.original_text,
                "status": r.status,
                "kind": r.kind,
                "original_at": r.original_at,
            }
            for r in rows
        ]
        return {"label": "bandeja", "count": len(items), "items": items}

    def _habits(self, today: date) -> list[dict[str, Any]]:
        habits = list(
            self.work.scalars(
                select(Habit).where(Habit.status == "active").order_by(Habit.name)
            )
        )
        cards: list[dict[str, Any]] = []
        for habit in habits:
            service = HabitService(self.work)
            quantities = service.quantities_by_date(habit.id, today, today)
            due = service.is_scheduled(habit, today)
            completed = service.is_met(habit, today, quantities)
            cards.append(
                {
                    "id": habit.id,
                    "name": habit.name,
                    "goal_type": habit.goal_type,
                    "due_today": due,
                    "completed_today": completed,
                    "current_streak": service.series(habit)["current_streak"],
                }
            )
        return cards

    def _finance(self, today: date) -> dict[str, Any]:
        if self.finance is None:
            return {"available": False}
        finance = FinanceDomainStore(self.finance)
        households = finance.list_households()
        if not households:
            return {"available": False}
        household = households[0]
        try:
            net = finance.net_worth(household.id)
            debts = finance.debt_summary(household.id)
            upcoming = finance.upcoming_payments(household.id, days=30, today=today)
        except Exception:
            return {
                "available": True,
                "household_id": household.id,
                "household_name": household.name,
            }
        return {
            "available": True,
            "household_id": household.id,
            "household_name": household.name,
            "total_balance": int(net.get("net_worth", 0) or 0),
            "active_debts": int(debts.get("count", 0) or 0),
            "upcoming_payments": len(upcoming.get("recurring_minimums", []))
            + len(upcoming.get("pending_installments", [])),
            "pending_installments": len(upcoming.get("pending_installments", [])),
        }