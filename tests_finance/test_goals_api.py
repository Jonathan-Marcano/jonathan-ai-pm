"""API de metas de ahorro (Fase UI-6)."""

import pytest
from fastapi.testclient import TestClient

from cuentafaro.api import create_app
from cuentafaro.db import create_engine_and_session
from cuentafaro.deps import get_session
from cuentafaro.models import Base


@pytest.fixture()
def client(tmp_path):
    engine, session_factory = create_engine_and_session(f"sqlite:///{tmp_path / 'goals.db'}")
    Base.metadata.create_all(engine)
    app = create_app()

    def override_session():
        session = session_factory()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_session] = override_session
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
    engine.dispose()


def _household(client):
    return client.post(
        "/api/v1/households",
        json={"name": "Hogar Metas", "timezone": "America/Santiago"},
    ).json()


def _goal(client, household_id, target=1_000_000, current=0, **extra):
    payload = {
        "name": "Vacaciones",
        "category": "travel",
        "target_amount": target,
        "current_amount": current,
        "monthly_contribution": 50_000,
        **extra,
    }
    return client.post(f"/api/v1/households/{household_id}/goals", json=payload)


def test_create_and_list_goals(client):
    household = _household(client)
    created = _goal(client, household["id"])
    assert created.status_code == 201
    goal = created.json()
    assert goal["name"] == "Vacaciones"
    assert goal["target_amount"] == 1_000_000
    assert goal["status"] == "active"

    listed = client.get(f"/api/v1/households/{household['id']}/goals")
    assert listed.status_code == 200
    assert len(listed.json()) == 1


def test_goals_are_isolated_by_household(client):
    h1 = _household(client)
    h2 = _household(client)
    _goal(client, h1["id"])
    _goal(client, h2["id"], name="Auto", target=5_000_000)
    assert len(client.get(f"/api/v1/households/{h1['id']}/goals").json()) == 1
    assert len(client.get(f"/api/v1/households/{h2['id']}/goals").json()) == 1


def test_contribute_marks_achieved(client):
    household = _household(client)
    goal = _goal(client, household["id"], target=100_000, current=60_000).json()
    after = client.post(f"/api/v1/goals/{goal['id']}/contributions", json={"amount": 50_000})
    assert after.status_code == 200
    body = after.json()
    assert body["current_amount"] == 110_000
    assert body["status"] == "achieved"


def test_update_goal(client):
    household = _household(client)
    goal = _goal(client, household["id"]).json()
    updated = client.patch(
        f"/api/v1/goals/{goal['id']}",
        json={"monthly_contribution": 120_000, "name": "Fondo de emergencia"},
    )
    assert updated.status_code == 200
    body = updated.json()
    assert body["name"] == "Fondo de emergencia"
    assert body["monthly_contribution"] == 120_000


def test_delete_goal(client):
    household = _household(client)
    goal = _goal(client, household["id"]).json()
    deleted = client.delete(f"/api/v1/goals/{goal['id']}")
    assert deleted.status_code == 204
    assert client.get(f"/api/v1/households/{household['id']}/goals").json() == []


def test_goal_requires_positive_target(client):
    household = _household(client)
    response = client.post(
        f"/api/v1/households/{household['id']}/goals",
        json={"name": "Meta inválida", "target_amount": 0},
    )
    assert response.status_code == 422