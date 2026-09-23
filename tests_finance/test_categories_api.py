"""API de categorías y fuentes de ingreso (CF1-06, CF1-07)."""

import pytest
from fastapi.testclient import TestClient

from cuentafaro.api import create_app
from cuentafaro.db import create_engine_and_session
from cuentafaro.deps import get_session
from cuentafaro.models import Base


@pytest.fixture()
def client(tmp_path):
    engine, session_factory = create_engine_and_session(f"sqlite:///{tmp_path / 'api3.db'}")
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
        json={"name": "Hogar Cat", "timezone": "America/Santiago"},
    ).json()


def test_household_creation_seeds_default_categories(client) -> None:
    household = _household(client)
    listed = client.get(f"/api/v1/households/{household['id']}/categories")
    assert listed.status_code == 200
    categories = listed.json()
    kinds = {c["kind"] for c in categories}
    assert kinds == {"expense", "income", "transfer"}
    assert len(categories) == 13


def test_create_custom_category(client) -> None:
    household = _household(client)
    response = client.post(
        f"/api/v1/households/{household['id']}/categories",
        json={"name": "Mascotas", "kind": "expense"},
    )
    assert response.status_code == 201
    assert response.json()["id"].startswith("cat_")
    assert response.json()["kind"] == "expense"


def test_duplicate_category_conflict(client) -> None:
    household = _household(client)
    payload = {"name": "Viajes", "kind": "expense"}
    assert (
        client.post(f"/api/v1/households/{household['id']}/categories", json=payload).status_code
        == 201
    )
    response = client.post(f"/api/v1/households/{household['id']}/categories", json=payload)
    assert response.status_code == 409


def test_update_category(client) -> None:
    household = _household(client)
    category = client.post(
        f"/api/v1/households/{household['id']}/categories", json={"name": "Gimnasio"}
    ).json()
    response = client.patch(f"/api/v1/categories/{category['id']}", json={"status": "inactive"})
    assert response.status_code == 200
    assert response.json()["status"] == "inactive"


def test_category_requires_household(client) -> None:
    response = client.post("/api/v1/households/hh_inexistente/categories", json={"name": "X"})
    assert response.status_code == 404


def test_create_income_source(client) -> None:
    household = _household(client)
    member = client.post(
        f"/api/v1/households/{household['id']}/members",
        json={"name": "Jonathan", "role": "admin"},
    ).json()
    response = client.post(
        f"/api/v1/households/{household['id']}/income-sources",
        json={
            "member_id": member["id"],
            "name": "Sueldo principal",
            "type": "salary",
            "expected_amount": 2200000,
            "frequency": "monthly",
        },
    )
    assert response.status_code == 201
    source = response.json()
    assert source["id"].startswith("inc_")
    assert source["expected_amount"] == 2200000
    assert isinstance(source["expected_amount"], int)


def test_income_source_rejects_member_from_other_household(client) -> None:
    household = _household(client)
    other = client.post(
        "/api/v1/households",
        json={"name": "Hogar Ajeno", "timezone": "America/Santiago", "status": "paused"},
    ).json()
    member = client.post(f"/api/v1/households/{other['id']}/members", json={"name": "Ajeno"}).json()
    response = client.post(
        f"/api/v1/households/{household['id']}/income-sources",
        json={"member_id": member["id"], "name": "Sueldo", "expected_amount": 1000000},
    )
    assert response.status_code == 422


def test_income_source_negative_amount_rejected(client) -> None:
    household = _household(client)
    response = client.post(
        f"/api/v1/households/{household['id']}/income-sources",
        json={"name": "Bono", "expected_amount": -500},
    )
    assert response.status_code == 422


def test_list_and_update_income_source(client) -> None:
    household = _household(client)
    source = client.post(
        f"/api/v1/households/{household['id']}/income-sources",
        json={"name": "Freelance", "type": "extra", "expected_amount": 300000},
    ).json()
    listed = client.get(f"/api/v1/households/{household['id']}/income-sources")
    assert len(listed.json()) == 1

    response = client.patch(
        f"/api/v1/income-sources/{source['id']}", json={"expected_amount": 350000}
    )
    assert response.status_code == 200
    assert response.json()["expected_amount"] == 350000


def test_delete_income_source(client) -> None:
    household = _household(client)
    source = client.post(
        f"/api/v1/households/{household['id']}/income-sources",
        json={"name": "Arriendo", "expected_amount": 500000},
    ).json()
    assert client.delete(f"/api/v1/income-sources/{source['id']}").status_code == 204
    listed = client.get(f"/api/v1/households/{household['id']}/income-sources")
    assert listed.json() == []
    assert len(listed.json()) == 0
