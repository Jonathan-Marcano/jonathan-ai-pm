import json
from datetime import date, datetime
from pathlib import Path

from sqlalchemy.orm import Session

from jonathan_ai_pm.services import DomainStore

ENTITY_ORDER = (
    ("workspaces", "workspace"),
    ("clients", "client"),
    ("projects", "project"),
    ("deliverables", "deliverable"),
    ("tasks", "task"),
    ("meetings", "meeting"),
    ("action_items", "action_item"),
    ("captures", "capture"),
    ("work_logs", "work_log"),
)


def load_snapshot(session: Session, path: Path) -> None:
    payload = json.loads(path.read_text(encoding="utf-8"))
    store = DomainStore(session)
    for collection, kind in ENTITY_ORDER:
        for raw_record in payload[collection]:
            record = {key: _coerce_temporal(key, value) for key, value in raw_record.items()}
            if kind == "task":
                record.pop("source_action_item_id", None)
            store.create(kind, **record)


def _coerce_temporal(key: str, value):
    if value is None:
        return None
    if key == "due_at":
        return date.fromisoformat(value)
    if key in {"starts_at", "started_at"}:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    return value
