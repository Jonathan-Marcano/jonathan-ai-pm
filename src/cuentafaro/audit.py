from __future__ import annotations

from datetime import date, datetime
from uuid import uuid4

from sqlalchemy import event, inspect
from sqlalchemy.orm import Session

from cuentafaro.models import AuditEvent

_listener_installed_factories = set()

ACTOR_KEY = "cuentafaro_actor"


def _session_actor(session: Session) -> str | None:
    return session.info.get(ACTOR_KEY)


def _json_safe(value):
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    return value


class AuditListener:
    """Escribe AuditEvent en el mismo flush para cada entidad mapeada."""

    def __init__(self) -> None:
        self._kinds_by_class = {}

    def _kind_for(self, instance) -> str:
        table_name = getattr(instance.__class__, "__tablename__", None)
        return table_name or instance.__class__.__name__

    @staticmethod
    def _new_id() -> str:
        return f"aev_{uuid4().hex}"

    def after_flush(self, session: Session, _flush_context) -> None:
        actor = _session_actor(session)
        stamps = []
        for instance in session.new:
            if isinstance(instance, AuditEvent):
                continue
            changes = self._column_values(instance)
            stamps.append((instance, "create", changes))
        for instance in session.dirty:
            if isinstance(instance, AuditEvent):
                continue
            changes = self._changed_columns(instance)
            if changes:
                stamps.append((instance, "update", changes))
        for instance in session.deleted:
            if isinstance(instance, AuditEvent):
                continue
            stamps.append((instance, "delete", {}))
        for instance, action, changes in stamps:
            session.add(
                AuditEvent(
                    id=self._new_id(),
                    entity_kind=self._kind_for(instance),
                    entity_id=str(instance.id),
                    action=action,
                    actor=actor,
                    changes=changes or {},
                )
            )

    @staticmethod
    def _column_values(instance) -> dict:
        return {
            attr.key: _json_safe(getattr(instance, attr.key))
            for attr in instance.__mapper__.column_attrs
            if getattr(instance, attr.key) is not None
        }

    @staticmethod
    def _changed_columns(instance) -> dict:
        changes = {}
        for attr in inspect(instance).attrs:
            if attr.key in ("created_at", "updated_at"):
                continue
            history = attr.history
            if history.has_changes():
                value = history.added[0] if history.added else None
                if value is not None:
                    changes[attr.key] = _json_safe(value)
        return changes


def install_audit_listener(session_factory) -> None:
    if session_factory in _listener_installed_factories:
        return
    listener = AuditListener()
    event.listen(session_factory, "after_flush", listener.after_flush)
    _listener_installed_factories.add(session_factory)
