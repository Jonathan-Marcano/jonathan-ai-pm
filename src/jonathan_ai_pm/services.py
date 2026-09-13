from datetime import date
from typing import Any
from uuid import uuid4

from sqlalchemy import Select, select
from sqlalchemy.orm import Session

from jonathan_ai_pm.models import (
    MODEL_BY_KIND,
    ActionItem,
    Capture,
    Deliverable,
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
