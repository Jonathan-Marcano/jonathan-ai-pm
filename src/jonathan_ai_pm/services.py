from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from typing import Any
from uuid import uuid4
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy import Select, select
from sqlalchemy.orm import Session

from jonathan_ai_pm.models import (
    MODEL_BY_KIND,
    ActionItem,
    Capture,
    Deliverable,
    Meeting,
    Project,
    Task,
    WorkLog,
    utc_now,
)


class DomainRuleError(ValueError):
    pass


class DomainStore:
    """Small transaction boundary for Phase 1 manual-first CRUD."""

    def __init__(self, session: Session):
        self.session = session

    def create(self, kind: str, **attributes: Any):
        model = self._model(kind)
        entity = model(**attributes)
        if isinstance(entity, Task) and entity.status == "done":
            raise DomainRuleError("Use complete_task to enforce completion evidence")
        if isinstance(entity, Deliverable) and entity.status == "in_review":
            raise DomainRuleError("Use move_deliverable_to_review to enforce review evidence")
        self.session.add(entity)
        self._validate_links(entity)
        self.session.commit()
        self.session.refresh(entity)
        return entity

    def get(self, kind: str, entity_id: str):
        return self.session.get(self._model(kind), entity_id)

    def list(self, kind: str, **filters: Any):
        model = self._model(kind)
        statement = select(model)
        statement = self._apply_filters(statement, model, filters)
        return list(self.session.scalars(statement.order_by(model.id)))

    def update(self, kind: str, entity_id: str, **changes: Any):
        entity = self._required(kind, entity_id)
        if isinstance(entity, Task) and changes.get("status") == "done":
            raise DomainRuleError("Use complete_task to enforce completion evidence")
        if isinstance(entity, Deliverable) and changes.get("status") == "in_review":
            raise DomainRuleError("Use move_deliverable_to_review to enforce review evidence")
        for name, value in changes.items():
            if name in {"id", "created_at", "updated_at"} or not hasattr(entity, name):
                raise DomainRuleError(f"Field cannot be updated: {name}")
            setattr(entity, name, value)
        self._validate_links(entity)
        self.session.commit()
        self.session.refresh(entity)
        return entity

    def delete(self, kind: str, entity_id: str) -> None:
        entity = self._required(kind, entity_id)
        self.session.delete(entity)
        self.session.commit()

    def complete_task(self, task_id: str, completion_note: str | None = None) -> Task:
        task = self._required("task", task_id)
        has_work_log = self.session.scalar(
            select(WorkLog.id).where(WorkLog.task_id == task_id).limit(1)
        )
        if not completion_note and not has_work_log:
            raise DomainRuleError("A completed task requires a completion note or work log")
        task.completion_note = completion_note or task.completion_note
        task.status = "done"
        self.session.commit()
        self.session.refresh(task)
        return task

    def move_deliverable_to_review(self, deliverable_id: str) -> Deliverable:
        deliverable = self._required("deliverable", deliverable_id)
        if not deliverable.acceptance_criteria or not deliverable.evidence_url:
            raise DomainRuleError(
                "A deliverable in review requires acceptance criteria and an evidence URL"
            )
        deliverable.status = "in_review"
        self.session.commit()
        self.session.refresh(deliverable)
        return deliverable

    def create_task_from_action(
        self,
        action_item_id: str,
        task_id: str,
        priority: str = "medium",
        due_at: date | None = None,
        deliverable_id: str | None = None,
    ) -> Task:
        action = self._required("action_item", action_item_id)
        if action.task_id:
            raise DomainRuleError(f"Action item already links task: {action.task_id}")

        meeting = self._required("meeting", action.meeting_id)
        selected_deliverable_id = deliverable_id or action.deliverable_id
        if selected_deliverable_id:
            deliverable = self._required("deliverable", selected_deliverable_id)
            if deliverable.project_id != meeting.project_id:
                raise DomainRuleError("Task and deliverable must belong to the meeting project")

        task = Task(
            id=task_id,
            project_id=meeting.project_id,
            deliverable_id=selected_deliverable_id,
            title=action.title,
            status="ready",
            priority=priority,
            due_at=due_at,
        )
        self.session.add(task)
        self.session.flush()
        action.task_id = task.id
        action.deliverable_id = selected_deliverable_id
        action.status = "accepted"
        self.session.commit()
        self.session.refresh(task)
        return task

    def capture(self, text: str) -> Capture:
        capture = Capture(id=f"cap_{uuid4().hex}", text=text, status="inbox")
        self.session.add(capture)
        self.session.commit()
        self.session.refresh(capture)
        return capture

    def morning_brief(
        self,
        timezone_name: str,
        brief_date: date | None = None,
        due_soon_days: int = 3,
        now: datetime | None = None,
    ) -> dict[str, Any]:
        if not 0 <= due_soon_days <= 30:
            raise DomainRuleError("due_soon_days must be between 0 and 30")
        try:
            local_timezone = ZoneInfo(timezone_name)
        except ZoneInfoNotFoundError as exc:
            raise DomainRuleError(f"Unknown timezone: {timezone_name}") from exc

        generated_at = now or datetime.now(UTC)
        if generated_at.tzinfo is None:
            generated_at = generated_at.replace(tzinfo=UTC)
        else:
            generated_at = generated_at.astimezone(UTC)
        target_date = brief_date or generated_at.astimezone(local_timezone).date()
        due_soon_through = target_date + timedelta(days=due_soon_days)

        tasks = self.list("task")
        open_tasks = [task for task in tasks if task.status not in {"done", "cancelled"}]
        overdue_tasks = self._sort_tasks(
            [task for task in open_tasks if task.due_at and task.due_at < target_date]
        )
        due_soon_tasks = self._sort_tasks(
            [
                task
                for task in open_tasks
                if task.due_at and target_date <= task.due_at <= due_soon_through
            ]
        )
        executable = [task for task in open_tasks if task.status in {"ready", "in_progress"}]
        focus_tasks = self._sort_tasks(executable)[:3]
        blocked_tasks = self._sort_tasks([task for task in open_tasks if task.status == "blocked"])

        meetings: list[Meeting] = [
            meeting
            for meeting in self.list("meeting", status="scheduled")
            if self._as_utc(meeting.starts_at).astimezone(local_timezone).date() == target_date
        ]
        meetings.sort(key=lambda meeting: self._as_utc(meeting.starts_at))

        deliverables = self.list("deliverable")
        blocked_deliverables = sorted(
            [item for item in deliverables if item.status == "blocked"],
            key=lambda item: (item.due_at, item.id),
        )
        in_progress_deliverable_ids = {
            task.deliverable_id
            for task in open_tasks
            if task.status == "in_progress" and task.deliverable_id
        }
        deliverable_opportunities = sorted(
            [
                item
                for item in deliverables
                if item.status in {"planned", "in_progress"}
                and item.id not in in_progress_deliverable_ids
            ],
            key=lambda item: (item.due_at, item.id),
        )[:5]
        at_risk_projects: list[Project] = sorted(
            [
                project
                for project in self.list("project")
                if project.health in {"at_risk", "off_track"}
                and project.status not in {"completed", "cancelled"}
            ],
            key=lambda project: (project.health != "off_track", project.id),
        )

        counts = {
            "meetings": len(meetings),
            "overdue_tasks": len(overdue_tasks),
            "due_soon_tasks": len(due_soon_tasks),
            "focus_tasks": len(focus_tasks),
            "blocked_tasks": len(blocked_tasks),
            "blocked_deliverables": len(blocked_deliverables),
            "deliverable_opportunities": len(deliverable_opportunities),
            "at_risk_projects": len(at_risk_projects),
        }
        return {
            "brief_date": target_date,
            "timezone": timezone_name,
            "due_soon_through": due_soon_through,
            "generated_at": generated_at,
            "counts": counts,
            "meetings": meetings,
            "overdue_tasks": overdue_tasks,
            "due_soon_tasks": due_soon_tasks,
            "focus_tasks": focus_tasks,
            "blocked_tasks": blocked_tasks,
            "blocked_deliverables": blocked_deliverables,
            "deliverable_opportunities": deliverable_opportunities,
            "at_risk_projects": at_risk_projects,
        }

    @staticmethod
    def _as_utc(value: datetime) -> datetime:
        return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)

    @staticmethod
    def _sort_tasks(tasks: list[Task]) -> list[Task]:
        priority_rank = {"critical": 0, "high": 1, "medium": 2, "low": 3}
        status_rank = {"in_progress": 0, "ready": 1, "blocked": 2, "inbox": 3}
        return sorted(
            tasks,
            key=lambda task: (
                priority_rank[task.priority],
                task.due_at or date.max,
                status_rank.get(task.status, 9),
                task.id,
            ),
        )

    def triage_capture(
        self,
        capture_id: str,
        disposition: str,
        *,
        project_id: str | None = None,
        task_id: str | None = None,
        action_item_id: str | None = None,
        meeting_id: str | None = None,
        deliverable_id: str | None = None,
        owner: str | None = None,
        priority: str = "medium",
        due_at: date | None = None,
        note: str | None = None,
    ) -> Capture:
        capture = self._required("capture", capture_id)
        if capture.status != "inbox":
            raise DomainRuleError("Capture has already been triaged")

        if disposition == "task":
            if not project_id or not task_id:
                raise DomainRuleError("Task triage requires project_id and task_id")
            task = Task(
                id=task_id,
                project_id=project_id,
                deliverable_id=deliverable_id,
                title=capture.text,
                status="ready",
                priority=priority,
                due_at=due_at,
            )
            self.session.add(task)
            self._validate_links(task)
            self.session.flush()
            capture.project_id = project_id
            capture.task_id = task.id

        elif disposition == "action":
            if not meeting_id or not action_item_id or not owner:
                raise DomainRuleError(
                    "Action triage requires meeting_id, action_item_id, and owner"
                )
            meeting = self._required("meeting", meeting_id)
            if project_id and project_id != meeting.project_id:
                raise DomainRuleError("Capture project must match the meeting project")
            action = ActionItem(
                id=action_item_id,
                meeting_id=meeting_id,
                deliverable_id=deliverable_id,
                title=capture.text,
                status="captured",
                owner=owner,
            )
            self.session.add(action)
            self._validate_links(action)
            self.session.flush()
            capture.project_id = meeting.project_id
            capture.action_item_id = action.id

        elif disposition in {"reference", "dismissed"}:
            if project_id:
                self._required("project", project_id)
            capture.project_id = project_id
        else:
            raise DomainRuleError(f"Unknown capture disposition: {disposition}")

        capture.status = "triaged"
        capture.disposition = disposition
        capture.disposition_note = note
        capture.triaged_at = utc_now()
        self.session.commit()
        self.session.refresh(capture)
        return capture

    @staticmethod
    def _apply_filters(statement: Select, model, filters: dict[str, Any]) -> Select:
        for name, value in filters.items():
            if value is None:
                continue
            if name.endswith("_from"):
                field_name = name.removesuffix("_from")
                statement = statement.where(getattr(model, field_name) >= value)
            elif name.endswith("_to"):
                field_name = name.removesuffix("_to")
                statement = statement.where(getattr(model, field_name) <= value)
            elif not hasattr(model, name):
                raise DomainRuleError(f"Unknown filter for {model.__tablename__}: {name}")
            else:
                statement = statement.where(getattr(model, name) == value)
        return statement

    @staticmethod
    def _model(kind: str):
        try:
            return MODEL_BY_KIND[kind]
        except KeyError as exc:
            raise DomainRuleError(f"Unknown entity kind: {kind}") from exc

    def _required(self, kind: str, entity_id: str):
        entity = self.get(kind, entity_id)
        if entity is None:
            raise DomainRuleError(f"{kind} not found: {entity_id}")
        return entity

    def _validate_links(self, entity) -> None:
        if isinstance(entity, Task) and entity.deliverable_id:
            deliverable = self._required("deliverable", entity.deliverable_id)
            if deliverable.project_id != entity.project_id:
                raise DomainRuleError("Task and deliverable must belong to the same project")

        if isinstance(entity, ActionItem):
            meeting = self._required("meeting", entity.meeting_id)
            if entity.task_id:
                task = self._required("task", entity.task_id)
                if task.project_id != meeting.project_id:
                    raise DomainRuleError("Action item and task must belong to the same project")
            if entity.deliverable_id:
                deliverable = self._required("deliverable", entity.deliverable_id)
                if deliverable.project_id != meeting.project_id:
                    raise DomainRuleError(
                        "Action item and deliverable must belong to the same project"
                    )
