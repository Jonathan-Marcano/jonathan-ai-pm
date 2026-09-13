from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from jonathan_ai_pm.models import MODEL_BY_KIND, Deliverable, Task, WorkLog


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
        self.session.commit()
        self.session.refresh(entity)
        return entity

    def get(self, kind: str, entity_id: str):
        return self.session.get(self._model(kind), entity_id)

    def list(self, kind: str):
        model = self._model(kind)
        return list(self.session.scalars(select(model).order_by(model.id)))

    def update(self, kind: str, entity_id: str, **changes: Any):
        entity = self._required(kind, entity_id)
        for name, value in changes.items():
            if name in {"id", "created_at", "updated_at"} or not hasattr(entity, name):
                raise DomainRuleError(f"Field cannot be updated: {name}")
            setattr(entity, name, value)
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
