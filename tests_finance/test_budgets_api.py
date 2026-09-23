"""API de presupuesto mensual (CF1-12)."""

import pytest
from fastapi.testclient import TestClient

from cuentafaro.api import create_app
from cuentafaro.db import create_engine_and_session
from cuentafaro.deps import get_session
from cuentafaro.models import Base


@pytest.fixture()
def client(tmp_path):
    engine, session_factory = create_engine_and_session(f"sqlite:///{tmp_path / 'api6.db'}")
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
        json={"name": "Hogar Presupuesto", "timezone": "America/Santiago"},
    ).json()


def _category(client, household_id, name="Alimentación"):
    categories = client.get(f"/api/v1/households/{household_id}/categories").json()
    for category in categories:
        if category["name"] == name and category["kind"] == "expense":
            return category
    return client.post(
        f"/api/v1/households/{household_id}/categories",
        json={"name": name, "kind": "expense"},
    ).json()


def _budget(client, household_id, phase="draft"):
    response = client.post(
        f"/api/v1/households/{household_id}/budgets",
        json={"year": 2026, "month": 9, "status": phase},
    )
    assert response.status_code == 201
    if phase == "draft":
        client.patch(f"/api/v1/budgets/{response.json()['id']}", json={"status": "active"})
    return response.json()


def test_create_budget(client) -> None:
    household = _household(client)
    budget = _budget(client, household["id"])
    assert budget["id"].startswith("bud_")
    assert budget["year"] == 2026 and budget["month"] == 9


def test_duplicate_budget_period_conflict(client) -> None:
    household = _household(client)
    _budget(client, household["id"])
    response = client.post(
        f"/api/v1/households/{household['id']}/budgets",
        json={"year": 2026, "month": 9},
    )
    assert response.status_code == 422


def test_set_budget_category(client) -> None:
    household = _household(client)
    budget = _budget(client, household["id"])
    category = _category(client, household["id"])
    response = client.post(
        f"/api/v1/budgets/{budget['id']}/categories",
        json={"category_id": category["id"], "planned_amount": 400000},
    )
    assert response.status_code == 201
    assert response.json()["planned_amount"] == 400000
    assert response.json()["actual_amount"] == 0


def test_budget_rejects_income_category(client) -> None:
    household = _household(client)
    budget = _budget(client, household["id"])
    income_category = client.post(
        f"/api/v1/households/{household['id']}/categories",
        json={"name": "Sueldo", "kind": "income"},
    ).json()
    response = client.post(
        f"/api/v1/budgets/{budget['id']}/categories",
        json={"category_id": income_category["id"], "planned_amount": 100},
    )
    assert response.status_code == 422


def test_expense_updates_budget_actuals(client) -> None:
    household = _household(client)
    account = client.post(
        "/api/v1/accounts",
        json={
            "household_id": household["id"],
            "name": "Cta",
            "type": "checking",
            "balance_reported": 500000,
        },
    ).json()
    budget = _budget(client, household["id"])
    category = _category(client, household["id"])
    client.post(
        f"/api/v1/budgets/{budget['id']}/categories",
        json={"category_id": category["id"], "planned_amount": 400000},
    )
    client.post(
        "/api/v1/transactions",
        json={
            "account_id": account["id"],
            "category_id": category["id"],
            "type": "expense",
            "amount": 25000,
            "date": "2026-09-05",
        },
    )
    rows = client.get(f"/api/v1/budgets/{budget['id']}/categories").json()
    assert rows[0]["actual_amount"] == 25000


def test_expense_outside_active_budget_not_tracked(client) -> None:
    household = _household(client)
    account = client.post(
        "/api/v1/accounts",
        json={
            "household_id": household["id"],
            "name": "Cta",
            "type": "checking",
            "balance_reported": 500000,
        },
    ).json()
    category = _category(client, household["id"])
    response = client.post(
        "/api/v1/transactions",
        json={
            "account_id": account["id"],
            "category_id": category["id"],
            "type": "expense",
            "amount": 25000,
            "date": "2026-09-05",
        },
    )
    assert response.status_code == 201


def test_voiding_expense_walks_back_budget_actuals(client) -> None:
    household = _household(client)
    account = client.post(
        "/api/v1/accounts",
        json={
            "household_id": household["id"],
            "name": "Cta",
            "type": "checking",
            "balance_reported": 500000,
        },
    ).json()
    budget = _budget(client, household["id"])
    category = _category(client, household["id"])
    client.post(
        f"/api/v1/budgets/{budget['id']}/categories",
        json={"category_id": category["id"], "planned_amount": 400000},
    )
    transaction = client.post(
        "/api/v1/transactions",
        json={
            "account_id": account["id"],
            "category_id": category["id"],
            "type": "expense",
            "amount": 10000,
            "date": "2026-09-05",
        },
    ).json()
    client.post(f"/api/v1/transactions/{transaction['id']}/void")
    rows = client.get(f"/api/v1/budgets/{budget['id']}/categories").json()
    assert rows[0]["actual_amount"] == 0
