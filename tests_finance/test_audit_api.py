"""Auditoría inmutable (CF1-20)."""

import pytest
from fastapi import Request
from fastapi.testclient import TestClient
from sqlalchemy import func, select, text
from sqlalchemy.exc import SQLAlchemyError

from cuentafaro.api import create_app
from cuentafaro.audit import ACTOR_KEY
from cuentafaro.db import create_engine_and_session
from cuentafaro.deps import get_session
from cuentafaro.models import AuditEvent, Base


@pytest.fixture()
def env(tmp_path):
    engine, session_factory = create_engine_and_session(f"sqlite:///{tmp_path / 'audit.db'}")
    Base.metadata.create_all(engine)
    with engine.begin() as connection:
        connection.execute(
            text(
                "CREATE TRIGGER audit_events_no_update "
                "BEFORE UPDATE ON audit_events FOR EACH ROW "
                "BEGIN SELECT RAISE(ABORT, 'audit_events is immutable'); END;"
            )
        )
        connection.execute(
            text(
                "CREATE TRIGGER audit_events_no_delete "
                "BEFORE DELETE ON audit_events FOR EACH ROW "
                "BEGIN SELECT RAISE(ABORT, 'audit_events is immutable'); END;"
            )
        )
    app = create_app()

    def override_session(request: Request):
        session = session_factory()
        session.info[ACTOR_KEY] = (request.headers.get("X-Actor") or "").strip() or None
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_session] = override_session
    with TestClient(app) as client:
        yield client, session_factory, engine
    app.dependency_overrides.clear()
    engine.dispose()


def _count_events(session_factory, action=None):
    with session_factory() as session:
        statement = select(func.count(AuditEvent.id))
        if action:
            statement = statement.where(AuditEvent.action == action)
        return session.scalar(statement) or 0


def test_create_is_audited_with_actor(env) -> None:
    client, _, _ = env
    headers = {"X-Actor": "Jonathan"}
    response = client.post(
        "/api/v1/households",
        json={"name": "Hogar Auditado", "timezone": "America/Santiago"},
        headers=headers,
    )
    assert response.status_code == 201
    with _session(env) as session:
        event = session.scalar(select(AuditEvent).where(AuditEvent.action == "create"))
        assert event is not None
        assert event.actor == "Jonathan"
        assert event.entity_kind == "households"
        assert event.entity_id == response.json()["id"]


def _session(env):
    return env[1]()


def test_update_is_audited_with_changes(env) -> None:
    client, session_factory, _ = env
    household = client.post(
        "/api/v1/households",
        json={"name": "Hogar A", "timezone": "America/Santiago"},
    ).json()
    client.patch(f"/api/v1/households/{household['id']}", json={"name": "Hogar Renombrado"})
    with session_factory() as session:
        update = session.scalar(
            select(AuditEvent).where(
                AuditEvent.action == "update", AuditEvent.entity_id == household["id"]
            )
        )
        assert update is not None
        assert update.changes.get("name") == "Hogar Renombrado"

    with session_factory() as session:
        created = session.scalar(
            select(AuditEvent).where(
                AuditEvent.action == "create", AuditEvent.entity_id == household["id"]
            )
        )
        assert created is not None


def test_audit_events_cannot_be_updated_or_deleted(env) -> None:
    client, session_factory, engine = env
    client.post(
        "/api/v1/households",
        json={"name": "Hogar B", "timezone": "America/Santiago"},
    )
    with engine.connect() as connection:
        with pytest.raises(SQLAlchemyError):
            connection.execute(text("UPDATE audit_events SET actor = 'hacker' WHERE 1=1"))
            connection.commit()
    with engine.connect() as connection:
        with pytest.raises(SQLAlchemyError):
            connection.execute(text("DELETE FROM audit_events WHERE entity_kind = 'households'"))
            connection.commit()


def test_deletion_of_orphan_is_audited(env) -> None:
    client, session_factory, _ = env
    household = client.post(
        "/api/v1/households",
        json={"name": "Hogar C", "timezone": "America/Santiago"},
    ).json()
    member = client.post(
        f"/api/v1/households/{household['id']}/members", json={"name": "Temporal"}
    ).json()
    with session_factory() as session:
        from cuentafaro.models import HouseholdMember

        row = session.get(HouseholdMember, member["id"])
        session.delete(row)
        session.commit()
    with session_factory() as session:
        event = session.scalar(
            select(AuditEvent).where(
                AuditEvent.action == "delete", AuditEvent.entity_id == member["id"]
            )
        )
        assert event is not None
        assert event.entity_kind == "household_members"


def test_audit_can_be_read_via_api(env) -> None:
    client, _, _ = env
    client.post(
        "/api/v1/households",
        json={"name": "Hogar Auditado", "timezone": "America/Santiago"},
        headers={"X-Actor": "Jonathan"},
    )
    response = client.get("/api/v1/audit")
    assert response.status_code == 200
    events = response.json()
    assert any(e["actor"] == "Jonathan" for e in events)
    by_kind = client.get("/api/v1/audit?entity_kind=households")
    assert any(e["entity_kind"] == "households" for e in by_kind.json())
    created = client.get("/api/v1/audit?action=create")
    assert any(e["action"] == "create" for e in created.json())
