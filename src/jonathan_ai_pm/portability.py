from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from jonathan_ai_pm.models import MODEL_BY_KIND, AuditEvent, utc_now
from jonathan_ai_pm.schemas import SnapshotDocument
from jonathan_ai_pm.services import DomainRuleError

COLLECTIONS = (
    ("workspace", "workspaces"),
    ("client", "clients"),
    ("project", "projects"),
    ("deliverable", "deliverables"),
    ("task", "tasks"),
    ("meeting", "meetings"),
    ("action_item", "action_items"),
    ("work_log", "work_logs"),
    ("capture", "captures"),
)


def export_snapshot(session: Session) -> dict[str, Any]:
    entities = {
        collection: list(
            session.scalars(select(MODEL_BY_KIND[kind]).order_by(MODEL_BY_KIND[kind].id))
        )
        for kind, collection in COLLECTIONS
    }
    entities["audit_events"] = list(
        session.scalars(select(AuditEvent).order_by(AuditEvent.occurred_at, AuditEvent.id))
    )
    return {
        "schema_version": "1.0",
        "exported_at": utc_now(),
        "entities": entities,
    }


def import_snapshot(session: Session, snapshot: SnapshotDocument) -> dict[str, Any]:
    models = [MODEL_BY_KIND[kind] for kind, _collection in COLLECTIONS]
    if any(session.scalar(select(model.id).limit(1)) is not None for model in models):
        raise DomainRuleError("Snapshot import requires an empty datastore")
    if session.scalar(select(AuditEvent.id).limit(1)) is not None:
        raise DomainRuleError("Snapshot import requires an empty datastore")

    previous_suppression = session.info.get("suppress_audit")
    session.info["suppress_audit"] = True
    try:
        for kind, collection in COLLECTIONS:
            model = MODEL_BY_KIND[kind]
            records = getattr(snapshot.entities, collection)
            session.add_all(model(**record.model_dump()) for record in records)
            session.flush()
        session.add_all(
            AuditEvent(**record.model_dump()) for record in snapshot.entities.audit_events
        )
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        if previous_suppression is None:
            session.info.pop("suppress_audit", None)
        else:
            session.info["suppress_audit"] = previous_suppression

    imported = {
        collection: len(getattr(snapshot.entities, collection))
        for _kind, collection in COLLECTIONS
    }
    imported["audit_events"] = len(snapshot.entities.audit_events)
    return {"schema_version": snapshot.schema_version, "imported": imported}
