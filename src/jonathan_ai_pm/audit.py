from __future__ import annotations

from datetime import date, datetime
from typing import Any
from uuid import uuid4

from sqlalchemy import event, inspect, select
from sqlalchemy.orm import Session

from jonathan_ai_pm.models import AuditEvent, MODEL_BY_KIND, utc_now

ENTITY_KIND_BY_MODEL = {model: kind for kind, model in MODEL_BY_KIND.items()}
IGNORED_CHANGE_FIELDS = {"created_at", "updated_at"}


def _json_value(value: Any) -> Any:
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if value is None or isinstance(value, (bool, int, float, str, list, dict)):
        return value
    return str(value)


def _creation_changes(entity: Any) -> dict[str, dict[str, Any]]:
    return {
        column.key: {"old": None, "new": _json_value(getattr(entity, column.key))}
        for column in inspect(entity).mapper.columns
        if column.key not in IGNORED_CHANGE_FIELDS
    }


def _update_changes(entity: Any) -> dict[str, dict[str, Any]]:
    state = inspect(entity)
    changes = {}
    for column in state.mapper.columns:
        if column.key in IGNORED_CHANGE_FIELDS:
            continue
        history = state.attrs[column.key].history
        if history.has_changes():
            old_value = history.deleted[0] if history.deleted else None
            new_value = history.added[0] if history.added else getattr(entity, column.key)
            changes[column.key] = {
                "old": _json_value(old_value),
                "new": _json_value(new_value),
            }
    return changes


def _deletion_changes(entity: Any) -> dict[str, dict[str, Any]]:
    return {
        column.key: {"old": _json_value(getattr(entity, column.key)), "new": None}
        for column in inspect(entity).mapper.columns
        if column.key not in IGNORED_CHANGE_FIELDS
    }


@event.listens_for(Session, "before_flush")
def record_audit_events(session: Session, _flush_context, _instances) -> None:
    if session.info.get("suppress_audit"):
        return

    actor = str(session.info.get("actor") or "local-user").strip()[:200] or "local-user"
    candidates = (
        [(entity, "create") for entity in list(session.new)]
        + [(entity, "update") for entity in list(session.dirty)]
        + [(entity, "delete") for entity in list(session.deleted)]
    )
    for entity, action in candidates:
        entity_kind = ENTITY_KIND_BY_MODEL.get(type(entity))
        if not entity_kind or isinstance(entity, AuditEvent):
            continue
        if action == "create":
            changes = _creation_changes(entity)
        elif action == "update":
            changes = _update_changes(entity)
        else:
            changes = _deletion_changes(entity)
        if not changes:
            continue
        session.add(
            AuditEvent(
                id=f"aud_{uuid4().hex}",
                entity_kind=entity_kind,
                entity_id=entity.id,
                action=action,
                actor=actor,
                occurred_at=utc_now(),
                changes=changes,
            )
        )


def list_audit_events(
    session: Session,
    *,
    entity_kind: str | None = None,
    entity_id: str | None = None,
    actor: str | None = None,
) -> list[AuditEvent]:
    statement = select(AuditEvent)
    if entity_kind:
        statement = statement.where(AuditEvent.entity_kind == entity_kind)
    if entity_id:
        statement = statement.where(AuditEvent.entity_id == entity_id)
    if actor:
        statement = statement.where(AuditEvent.actor == actor)
    return list(session.scalars(statement.order_by(AuditEvent.occurred_at, AuditEvent.id)))
