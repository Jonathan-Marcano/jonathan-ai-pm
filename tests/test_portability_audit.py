from copy import deepcopy

import pytest
from pydantic import ValidationError
from sqlalchemy.orm import Session

from faroflow.db import build_engine
from faroflow.models import Base
from faroflow.portability import export_snapshot, import_snapshot
from faroflow.schemas import SnapshotDocument


def create_hierarchy(api_client, headers=None) -> None:
    headers = headers or {}
    assert (
        api_client.post(
            "/api/v1/workspaces",
            headers=headers,
            json={
                "id": "wrk_demo",
                "name": "Demo workspace",
                "timezone": "America/Santiago",
            },
        ).status_code
        == 201
    )
    assert (
        api_client.post(
            "/api/v1/clients",
            headers=headers,
            json={"id": "cli_demo", "workspace_id": "wrk_demo", "name": "Demo client"},
        ).status_code
        == 201
    )
    assert (
        api_client.post(
            "/api/v1/projects",
            headers=headers,
            json={"id": "prj_demo", "client_id": "cli_demo", "name": "Demo project"},
        ).status_code
        == 201
    )


def test_audit_records_actor_and_field_changes(api_client) -> None:
    headers = {"X-Actor": "jonathan"}
    create_hierarchy(api_client, headers)
    api_client.post(
        "/api/v1/deliverables",
        headers=headers,
        json={
            "id": "del_demo",
            "project_id": "prj_demo",
            "title": "Demo plan",
            "due_at": "2026-09-18",
        },
    )
    api_client.post(
        "/api/v1/tasks",
        headers=headers,
        json={"id": "tsk_demo", "project_id": "prj_demo", "title": "Draft plan"},
    )

    updated = api_client.patch(
        "/api/v1/tasks/tsk_demo",
        headers=headers,
        json={
            "deliverable_id": "del_demo",
            "due_at": "2026-09-20",
            "status": "ready",
        },
    )
    assert updated.status_code == 200

    response = api_client.get(
        "/api/v1/audit-events?entity_kind=task&entity_id=tsk_demo&actor=jonathan"
    )
    assert response.status_code == 200
    events = response.json()
    assert [event["action"] for event in events] == ["create", "update"]
    changes = events[-1]["changes"]
    assert changes["deliverable_id"] == {"old": None, "new": "del_demo"}
    assert changes["due_at"] == {"old": None, "new": "2026-09-20"}
    assert changes["status"] == {"old": "inbox", "new": "ready"}


def test_snapshot_round_trip_preserves_entities_and_audit(api_client) -> None:
    create_hierarchy(api_client, {"X-Actor": "jonathan"})
    exported = api_client.get("/api/v1/snapshots/export")
    assert exported.status_code == 200
    payload = exported.json()
    assert payload["schema_version"] == "1.1"
    assert len(payload["entities"]["audit_events"]) == 3

    engine = build_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as target:
        result = import_snapshot(target, SnapshotDocument.model_validate(payload))
        restored = export_snapshot(target)

    assert result["imported"]["projects"] == 1
    assert result["imported"]["translations"] == 0
    assert result["imported"]["audit_events"] == 3
    assert restored["entities"]["projects"][0].name == "Demo project"
    assert [event.id for event in restored["entities"]["audit_events"]] == [
        event["id"] for event in payload["entities"]["audit_events"]
    ]


def test_snapshot_import_requires_empty_datastore(api_client) -> None:
    create_hierarchy(api_client)
    payload = api_client.get("/api/v1/snapshots/export").json()

    response = api_client.post("/api/v1/snapshots/import", json=payload)

    assert response.status_code == 422
    assert response.json()["detail"] == "Snapshot import requires an empty datastore"


def test_snapshot_validation_rejects_broken_graph(api_client) -> None:
    create_hierarchy(api_client)
    payload = deepcopy(api_client.get("/api/v1/snapshots/export").json())
    payload["entities"]["clients"][0]["workspace_id"] = "wrk_missing"

    with pytest.raises(ValidationError, match="unknown workspace"):
        SnapshotDocument.model_validate(payload)


def test_failed_transaction_leaves_no_audit_event(api_client) -> None:
    response = api_client.post(
        "/api/v1/clients",
        headers={"X-Actor": "jonathan"},
        json={"id": "cli_orphan", "workspace_id": "wrk_missing", "name": "Orphan"},
    )
    assert response.status_code == 409

    events = api_client.get("/api/v1/audit-events?entity_id=cli_orphan")
    assert events.status_code == 200
    assert events.json() == []
