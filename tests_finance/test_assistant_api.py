"""API del asistente con IA local (Fase 3, CF3-01..CF3-05)."""

import pytest
from fastapi.testclient import TestClient

from cuentafaro.api import create_app
from cuentafaro.db import create_engine_and_session
from cuentafaro.deps import get_session
from cuentafaro.models import Base


@pytest.fixture()
def client(tmp_path):
    engine, session_factory = create_engine_and_session(f"sqlite:///{tmp_path / 'api_ai.db'}")
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
        json={"name": "Hogar AI", "timezone": "America/Santiago", "status": "active"},
    ).json()


def _account(client, household_id):
    return client.post(
        "/api/v1/accounts",
        json={
            "household_id": household_id,
            "name": "Corriente",
            "type": "checking",
            "balance_reported": 5_000_000,
        },
    ).json()


def _expense_category(client, household_id, name="Alimentación"):
    categories = client.get(f"/api/v1/households/{household_id}/categories").json()
    return next(cat for cat in categories if cat["name"] == name)


def _transaction(client, account_id, *, amount, date, description, category_id=None):
    payload = {
        "account_id": account_id,
        "type": "expense",
        "amount": amount,
        "date": date,
        "description": description,
    }
    if category_id:
        payload["category_id"] = category_id
    response = client.post("/api/v1/transactions", json=payload)
    assert response.status_code == 201
    return response.json()


def _rule(client, household_id, category_id, pattern):
    return client.post(
        f"/api/v1/households/{household_id}/import-category-rules",
        json={"column": "description", "pattern": pattern, "category_id": category_id},
    )


def _budget(client, household_id, year, month):
    return client.post(
        f"/api/v1/households/{household_id}/budgets",
        json={"year": year, "month": month, "status": "active"},
    ).json()


def _budget_category(client, budget_id, category_id, planned_amount):
    response = client.post(
        f"/api/v1/budgets/{budget_id}/categories",
        json={"category_id": category_id, "planned_amount": planned_amount},
    )
    assert response.status_code == 201
    return response.json()


# ---------------- Sugerencia de categoría (CF3-01..CF3-03) ----------------


def test_suggest_category_uses_rule_and_creates_pending_proposal(client) -> None:
    household = _household(client)
    food = _expense_category(client, household["id"])
    _rule(client, household["id"], food["id"], pattern="santa isabel")

    response = client.post(
        f"/api/v1/households/{household['id']}/assistant/suggest-category",
        json={"description": "Compras en Santa Isabel", "amount": 45890},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["provider"] == "rule_based"
    assert len(body["suggestions"]) == 1
    suggestion = body["suggestions"][0]
    assert suggestion["category_id"] == food["id"]
    assert suggestion["category_name"] == "Alimentación"
    assert suggestion["confidence"] == 1.0
    assert suggestion["rank"] == 1

    proposal = body["proposal"]
    assert proposal["kind"] == "category_suggestion"
    assert proposal["status"] == "pending"
    assert proposal["payload"]["description"] == "Compras en Santa Isabel"
    assert proposal["payload"]["amount"] == 45890

    listed = client.get(f"/api/v1/households/{household['id']}/assistant/proposals").json()
    assert [item["id"] for item in listed] == [proposal["id"]]


def test_suggest_category_uses_memory_when_no_rule_matches(client) -> None:
    household = _household(client)
    account = _account(client, household["id"])
    food = _expense_category(client, household["id"])
    _transaction(
        client,
        account["id"],
        amount=5000,
        date="2026-08-10",
        description="Mercado del Valle",
        category_id=food["id"],
    )

    response = client.post(
        f"/api/v1/households/{household['id']}/assistant/suggest-category",
        json={"description": "Mercado del Valle hoy"},
    )
    assert response.status_code == 200
    suggestions = response.json()["suggestions"]
    assert len(suggestions) == 1
    assert suggestions[0]["category_id"] == food["id"]
    assert suggestions[0]["confidence"] == 0.6


def test_suggest_category_empty_without_signals(client) -> None:
    household = _household(client)
    response = client.post(
        f"/api/v1/households/{household['id']}/assistant/suggest-category",
        json={"description": "cosas aleatorias sin patron 987654"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["suggestions"] == []
    assert body["proposal"]["status"] == "pending"


def test_suggest_category_rejects_income_kind_category(client) -> None:
    household = _household(client)
    income = _expense_category(client, household["id"], name="Ingreso del trabajo")
    _rule(client, household["id"], income["id"], pattern="salario")

    response = client.post(
        f"/api/v1/households/{household['id']}/assistant/suggest-category",
        json={"description": "Salario mensual"},
    )
    assert response.status_code == 200
    assert response.json()["suggestions"] == []


# ---------------- Insights y anomalías (CF3-06, CF3-07) ----------------


def test_insights_report_budget_overrun(client) -> None:
    household = _household(client)
    account = _account(client, household["id"])
    food = _expense_category(client, household["id"])
    budget = _budget(client, household["id"], 2026, 9)
    _budget_category(client, budget["id"], food["id"], planned_amount=100_000)
    client.post(
        "/api/v1/transactions",
        json={
            "account_id": account["id"],
            "type": "income",
            "amount": 100_000,
            "date": "2026-09-01",
            "description": "Ingreso parcial",
        },
    )
    _transaction(
        client,
        account["id"],
        amount=150_000,
        date="2026-09-05",
        description="Supermercado",
        category_id=food["id"],
    )

    response = client.get(
        f"/api/v1/households/{household['id']}/assistant/insights?year=2026&month=9"
    )
    assert response.status_code == 200
    body = response.json()
    assert body["provider"] == "rule_based"
    assert body["period"] == "2026-09"
    titles = [insight["title"] for insight in body["insights"]]
    assert any("excedió" in title for title in titles)
    overrun = next(insight for insight in body["insights"] if "excedió" in insight["title"])
    assert overrun["severity"] == "warning"
    assert overrun["category_id"] == food["id"]
    assert any("gastó más" in title for title in titles)


def test_insights_create_monthly_insight_proposal_with_data(client) -> None:
    household = _household(client)
    account = _account(client, household["id"])
    client.post(
        "/api/v1/transactions",
        json={
            "account_id": account["id"],
            "type": "income",
            "amount": 150_000,
            "date": "2026-09-02",
            "description": "Ingreso",
        },
    )
    client.post(
        "/api/v1/transactions",
        json={
            "account_id": account["id"],
            "type": "expense",
            "amount": 20_000,
            "date": "2026-09-05",
            "description": "Mercado",
        },
    )
    url = f"/api/v1/households/{household['id']}/assistant/insights?year=2026&month=9"
    for _ in range(2):
        assert client.get(url).status_code == 200

    proposals = client.get(f"/api/v1/households/{household['id']}/assistant/proposals").json()
    insights = [item for item in proposals if item["kind"] == "insight"]
    assert len(insights) == 1
    assert insights[0]["status"] == "pending"
    assert insights[0]["payload"]["period"] == "2026-09"
    assert "Balance del mes" in insights[0]["payload"]["title"]


def test_insights_detect_anomaly_without_budget(client) -> None:
    household = _household(client)
    account = _account(client, household["id"])
    ocio = _expense_category(client, household["id"], name="Ocio")
    _transaction(
        client,
        account["id"],
        amount=50_000,
        date="2026-08-15",
        description="Indie Rock bar",
        category_id=ocio["id"],
    )
    _transaction(
        client,
        account["id"],
        amount=150_000,
        date="2026-09-05",
        description="Cena especial",
        category_id=ocio["id"],
    )

    body = client.get(
        f"/api/v1/households/{household['id']}/assistant/insights?year=2026&month=9"
    ).json()
    assert len(body["anomalies"]) == 1
    anomaly = body["anomalies"][0]
    assert anomaly["category_id"] == ocio["id"]
    assert anomaly["budget_id"] is None
    assert anomaly["suggested_planned_amount"] == 60_000

    proposals = client.get(f"/api/v1/households/{household['id']}/assistant/proposals").json()
    anomalies = [item for item in proposals if item["kind"] == "anomaly"]
    assert len(anomalies) == 1
    assert anomalies[0]["status"] == "pending"
    assert anomalies[0]["payload"]["period"] == "2026-09"
    assert anomalies[0]["payload"]["category_id"] == ocio["id"]


def test_insights_deduplicate_anomaly_proposals(client) -> None:
    household = _household(client)
    account = _account(client, household["id"])
    ocio = _expense_category(client, household["id"], name="Ocio")
    _transaction(
        client,
        account["id"],
        amount=50_000,
        date="2026-08-15",
        description="Bar",
        category_id=ocio["id"],
    )
    _transaction(
        client,
        account["id"],
        amount=150_000,
        date="2026-09-05",
        description="Cena especial",
        category_id=ocio["id"],
    )

    url = f"/api/v1/households/{household['id']}/assistant/insights?year=2026&month=9"
    for _ in range(2):
        assert client.get(url).status_code == 200

    proposals = client.get(f"/api/v1/households/{household['id']}/assistant/proposals").json()
    anomalies = [item for item in proposals if item["kind"] == "anomaly"]
    assert len(anomalies) == 1


def test_budget_adjust_proposal_apply_updates_plan(client) -> None:
    household = _household(client)
    account = _account(client, household["id"])
    ocio = _expense_category(client, household["id"], name="Ocio")
    budget = _budget(client, household["id"], 2026, 9)
    _budget_category(client, budget["id"], ocio["id"], planned_amount=40_000)
    _transaction(
        client,
        account["id"],
        amount=50_000,
        date="2026-08-15",
        description="Bar",
        category_id=ocio["id"],
    )
    _transaction(
        client,
        account["id"],
        amount=150_000,
        date="2026-09-05",
        description="Cena especial",
        category_id=ocio["id"],
    )

    body = client.get(
        f"/api/v1/households/{household['id']}/assistant/insights?year=2026&month=9"
    ).json()
    assert len(body["anomalies"]) == 1
    anomaly = body["anomalies"][0]
    assert anomaly["budget_id"] == budget["id"]

    proposals = client.get(f"/api/v1/households/{household['id']}/assistant/proposals").json()
    anomaly_proposal = next(item for item in proposals if item["kind"] == "anomaly")
    assert anomaly_proposal["payload"]["budget_id"] == budget["id"]
    assert anomaly_proposal["payload"]["suggested_planned_amount"] == 60_000

    adjust_proposal = next(item for item in proposals if item["kind"] == "budget_adjust")
    assert adjust_proposal["status"] == "pending"
    assert adjust_proposal["payload"]["category_id"] == ocio["id"]
    assert adjust_proposal["payload"]["suggested_planned_amount"] == 60_000

    resolved = client.post(
        f"/api/v1/assistant/proposals/{adjust_proposal['id']}/resolve",
        json={"resolution": "applied"},
    )
    assert resolved.status_code == 200
    assert resolved.json()["status"] == "applied"
    assert resolved.json()["payload"]["suggested_planned_amount"] == 60_000

    categories = client.get(f"/api/v1/budgets/{budget['id']}/categories").json()
    assert categories[0]["planned_amount"] == 60_000

    second = client.post(
        f"/api/v1/assistant/proposals/{adjust_proposal['id']}/resolve",
        json={"resolution": "dismissed"},
    )
    assert second.status_code == 422
    assert "ya fue procesada" in second.json()["detail"]

    still_pending_anomaly = client.get(
        f"/api/v1/households/{household['id']}/assistant/proposals?status=pending"
    ).json()
    assert anomaly_proposal["id"] in {item["id"] for item in still_pending_anomaly}
    assert adjust_proposal["id"] not in {item["id"] for item in still_pending_anomaly}


def test_resolve_category_suggestion_dismiss(client) -> None:
    household = _household(client)
    response = client.post(
        f"/api/v1/households/{household['id']}/assistant/suggest-category",
        json={"description": "Café en la esquina"},
    )
    proposal_id = response.json()["proposal"]["id"]

    dismissed = client.post(
        f"/api/v1/assistant/proposals/{proposal_id}/resolve",
        json={"resolution": "dismissed"},
    )
    assert dismissed.status_code == 200
    listed = client.get(
        f"/api/v1/households/{household['id']}/assistant/proposals?status=dismissed"
    ).json()
    assert [item["id"] for item in listed] == [proposal_id]


def test_proposals_reject_unknown_status(client) -> None:
    household = _household(client)
    response = client.get(f"/api/v1/households/{household['id']}/assistant/proposals?status=wat")
    assert response.status_code == 422
