"""API de hogares e integrantes (CF1-03)."""

import pytest
from fastapi.testclient import TestClient

from cuentafaro.api import create_app
from cuentafaro.db import create_engine_and_session
from cuentafaro.deps import get_session
from cuentafaro.models import Base


@pytest.fixture()
def client(tmp_path):
    engine, session_factory = create_engine_and_session(f"sqlite:///{tmp_path / 'api.db'}")
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


def _create_household(client, name="Hogar Prueba", status="active"):
    response = client.post(
        "/api/v1/households",
        json={"name": name, "timezone": "America/Santiago", "status": status},
    )
    assert response.status_code == 201
    return response.json()


def test_health_works(client) -> None:
    assert client.get("/health").status_code == 200


def test_create_household(client) -> None:
    payload = _create_household(client)
    assert payload["id"].startswith("hh_")
    assert payload["name"] == "Hogar Prueba"
    assert payload["status"] == "active"
    assert payload["timezone"] == "America/Santiago"


def test_creating_second_household_pauses_first(client) -> None:
    first = _create_household(client)
    second = _create_household(client, name="Otro")
    assert second["status"] == "active"
    assert client.get(f"/api/v1/households/{first['id']}").json()["status"] == "paused"

    activated = client.patch(f"/api/v1/households/{first['id']}", json={"status": "active"})
    assert activated.status_code == 200
    assert activated.json()["status"] == "active"
    assert client.get(f"/api/v1/households/{second['id']}").json()["status"] == "paused"


def test_cannot_create_household_with_empty_name(client) -> None:
    response = client.post(
        "/api/v1/households", json={"name": "   ", "timezone": "America/Santiago"}
    )
    assert response.status_code == 422


def test_get_and_update_household(client) -> None:
    created = _create_household(client)
    response = client.patch(
        f"/api/v1/households/{created['id']}", json={"name": "Hogar Renombrado"}
    )
    assert response.status_code == 200
    assert response.json()["name"] == "Hogar Renombrado"

    fetched = client.get(f"/api/v1/households/{created['id']}")
    assert fetched.status_code == 200
    assert fetched.json()["name"] == "Hogar Renombrado"


def test_get_missing_household_returns_404(client) -> None:
    assert client.get("/api/v1/households/hh_inexistente").status_code == 404


def test_create_and_list_members(client) -> None:
    household = _create_household(client)
    response = client.post(
        f"/api/v1/households/{household['id']}/members",
        json={"name": "Jonathan", "role": "admin", "status": "active"},
    )
    assert response.status_code == 201
    member = response.json()
    assert member["id"].startswith("mem_")
    assert member["household_id"] == household["id"]

    listed = client.get(f"/api/v1/households/{household['id']}/members")
    assert listed.status_code == 200
    assert len(listed.json()) == 1
    assert listed.json()[0]["name"] == "Jonathan"


def test_member_requires_existing_household(client) -> None:
    response = client.post("/api/v1/households/hh_inexistente/members", json={"name": "Juan"})
    assert response.status_code == 404


def test_create_member_with_empty_name(client) -> None:
    household = _create_household(client)
    response = client.post(f"/api/v1/households/{household['id']}/members", json={"name": "  "})
    assert response.status_code == 422


def test_update_member(client) -> None:
    household = _create_household(client)
    member = client.post(
        f"/api/v1/households/{household['id']}/members",
        json={"name": "Ana", "role": "member"},
    ).json()
    response = client.patch(f"/api/v1/members/{member['id']}", json={"role": "admin"})
    assert response.status_code == 200
    assert response.json()["role"] == "admin"
    assert response.json()["name"] == "Ana"


def test_update_missing_member_returns_404(client) -> None:
    assert client.patch("/api/v1/members/mem_inexistente", json={"name": "X"}).status_code == 404


def test_delete_member(client) -> None:
    household = _create_household(client)
    member = client.post(
        f"/api/v1/households/{household['id']}/members",
        json={"name": "Evelin", "role": "member"},
    ).json()
    response = client.delete(f"/api/v1/members/{member['id']}")
    assert response.status_code == 204
    assert client.get(f"/api/v1/members/{member['id']}").status_code == 404
    listed = client.get(f"/api/v1/households/{household['id']}/members")
    assert len(listed.json()) == 0


def test_delete_missing_member_returns_404(client) -> None:
    assert client.delete("/api/v1/members/mem_inexistente").status_code == 404


def test_delete_household_with_cascade(client) -> None:
    household = _create_household(client)
    member = client.post(
        f"/api/v1/households/{household['id']}/members",
        json={"name": "Jonathan", "role": "admin"},
    ).json()
    account = client.post(
        "/api/v1/accounts",
        json={
            "household_id": household["id"],
            "name": "Cuenta de prueba",
            "type": "checking",
            "balance_reported": 100000,
        },
    ).json()
    client.post(
        "/api/v1/transactions",
        json={
            "account_id": account["id"],
            "type": "expense",
            "amount": 15000,
            "date": "2026-09-15",
        },
    )

    response = client.delete(f"/api/v1/households/{household['id']}")
    assert response.status_code == 204
    assert client.get(f"/api/v1/households/{household['id']}").status_code == 404
    assert client.get(f"/api/v1/accounts/{account['id']}").status_code == 404
    assert client.get(f"/api/v1/members/{member['id']}").status_code == 404
    assert client.get("/api/v1/households").json() == []


def test_delete_missing_household_returns_404(client) -> None:
    assert client.delete("/api/v1/households/hh_inexistente").status_code == 404
