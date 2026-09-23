"""Dashboard, vencimientos, deudas, patrimonio y cierre mensual (CF1-13 a CF1-17)."""

from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient

from cuentafaro.api import create_app
from cuentafaro.db import create_engine_and_session
from cuentafaro.deps import get_session
from cuentafaro.models import Base


@pytest.fixture()
def client(tmp_path):
    engine, session_factory = create_engine_and_session(f"sqlite:///{tmp_path / 'api7.db'}")
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
        json={"name": "Hogar Reportes", "timezone": "America/Santiago"},
    ).json()


def _account(client, household_id, balance=1000000):
    return client.post(
        "/api/v1/accounts",
        json={
            "household_id": household_id,
            "name": "Cuenta principal",
            "type": "checking",
            "balance_reported": balance,
        },
    ).json()


def _debt(client, household_id, name="Tarjeta", original=500000, due_day=10):
    response = client.post(
        f"/api/v1/households/{household_id}/debts",
        json={
            "name": name,
            "type": "credit_card",
            "original_amount": original,
            "minimum_payment": 25000,
            "due_day": due_day,
        },
    )
    assert response.status_code == 201
    return response.json()


def _scenario(client):
    household = _household(client)
    account = _account(client, household["id"])
    category = client.post(
        f"/api/v1/households/{household['id']}/categories",
        json={"name": "Compras", "kind": "expense"},
    ).json()
    debt = _debt(client, household["id"])
    budget = client.post(
        f"/api/v1/households/{household['id']}/budgets",
        json={"year": 2026, "month": 9, "status": "active"},
    ).json()
    client.post(
        f"/api/v1/budgets/{budget['id']}/categories",
        json={"category_id": category["id"], "planned_amount": 500000},
    )
    for payload in [
        {"account_id": account["id"], "type": "income", "amount": 2000000, "date": "2026-09-05"},
        {
            "account_id": account["id"],
            "category_id": category["id"],
            "type": "expense",
            "amount": 400000,
            "date": "2026-09-10",
        },
    ]:
        assert client.post("/api/v1/transactions", json=payload).status_code == 201
    return household, account, debt


def test_dashboard_month_summary(client) -> None:
    household, _, _ = _scenario(client)
    response = client.get(f"/api/v1/households/{household['id']}/dashboard?year=2026&month=9")
    assert response.status_code == 200
    data = response.json()
    assert data["income"] == 2000000
    assert data["expenses"] == 400000
    assert data["balance"] == 1600000
    assert data["total_debt"] == 500000
    assert data["net_worth"] == 1000000 + 2000000 - 400000 - 500000
    assert len(data["budget"]) == 1
    assert data["budget"][0]["planned"] == 500000
    assert data["budget"][0]["actual"] == 400000


def test_dashboard_money_are_integers(client) -> None:
    household, _, _ = _scenario(client)
    data = client.get(f"/api/v1/households/{household['id']}/dashboard?year=2026&month=9").json()
    for field in ("income", "expenses", "balance", "total_debt", "net_worth"):
        assert isinstance(data[field], int)


def test_dashboard_expected_income_from_sources(client) -> None:
    household, _, _ = _scenario(client)
    client.post(
        f"/api/v1/households/{household['id']}/income-sources",
        json={"name": "Sueldo 1", "expected_amount": 1000000},
    )
    second = client.post(
        f"/api/v1/households/{household['id']}/income-sources",
        json={"name": "Sueldo 2", "expected_amount": 500000},
    ).json()
    client.post(
        f"/api/v1/households/{household['id']}/income-sources",
        json={"name": "Freelance", "status": "inactive", "expected_amount": 800000},
    )
    data = client.get(f"/api/v1/households/{household['id']}/dashboard?year=2026&month=9").json()
    assert data["expected_income"] == 1500000
    client.patch(f"/api/v1/income-sources/{second['id']}", json={"status": "inactive"})
    data = client.get(f"/api/v1/households/{household['id']}/dashboard?year=2026&month=9").json()
    assert data["expected_income"] == 1000000


def test_dashboard_monthly_series(client) -> None:
    household, _, _ = _scenario(client)
    data = client.get(f"/api/v1/households/{household['id']}/dashboard?year=2026&month=9").json()
    assert len(data["series"]) == 12
    september = data["series"][8]
    assert september["month"] == 9
    assert september["income"] == 2000000
    assert september["expenses"] == 400000
    assert september["balance"] == 1600000
    for entry in data["series"]:
        assert isinstance(entry["income"], int)
        assert isinstance(entry["expenses"], int)


def test_dashboard_expense_categories(client) -> None:
    household, _, _ = _scenario(client)
    data = client.get(f"/api/v1/households/{household['id']}/dashboard?year=2026&month=9").json()
    assert data["expense_categories"] == [{"name": "Compras", "amount": 400000}]
    other = client.get(f"/api/v1/households/{household['id']}/dashboard?year=2026&month=8").json()
    assert other["expense_categories"] == []


def test_debt_summary_totals(client) -> None:
    household, _, debt = _scenario(client)
    data = client.get(f"/api/v1/households/{household['id']}/debt-summary").json()
    assert data["total_current_balance"] == 500000
    assert data["total_original_amount"] == 500000
    assert data["by_status"]["active"]["count"] == 1


def test_net_worth(client) -> None:
    household, account, debt = _scenario(client)
    assert (
        client.post(
            f"/api/v1/debts/{debt['id']}/payments",
            json={"account_id": account["id"], "amount": 100000, "payment_date": "2026-09-10"},
        ).status_code
        == 201
    )
    data = client.get(f"/api/v1/households/{household['id']}/net-worth").json()
    assert data["assets"] == 1000000 + 2000000 - 400000 - 100000
    assert data["liabilities"] == 400000
    assert data["net_worth"] == data["assets"] - data["liabilities"]


def test_upcoming_installments(client) -> None:
    household, _, debt = _scenario(client)
    due = date.today() + timedelta(days=5)
    client.post(
        f"/api/v1/debts/{debt['id']}/installments",
        json={
            "due_date": due.isoformat(),
            "principal_amount": 45000,
            "interest_amount": 5000,
        },
    )
    client.post(
        f"/api/v1/debts/{debt['id']}/installments",
        json={
            "due_date": (date.today() + timedelta(days=200)).isoformat(),
            "principal_amount": 45000,
        },
    )
    data = client.get(f"/api/v1/households/{household['id']}/upcoming-payments?days=30").json()
    assert len(data["pending_installments"]) == 1
    assert data["pending_installments"][0]["days_left"] == 5


def test_recurring_minimums_listed(client) -> None:
    household, _, _ = _scenario(client)
    data = client.get(f"/api/v1/households/{household['id']}/upcoming-payments?days=60").json()
    assert len(data["recurring_minimums"]) >= 1
    assert data["recurring_minimums"][0]["debt_name"] == "Tarjeta"


def test_monthly_close_marks_installments(client) -> None:
    household, _, debt = _scenario(client)
    client.post(
        f"/api/v1/debts/{debt['id']}/installments",
        json={"due_date": "2026-09-20", "principal_amount": 30000},
    )
    response = client.post(
        f"/api/v1/households/{household['id']}/monthly-close", json={"year": 2026, "month": 9}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["budget_status"] == "closed"
    assert data["installments_in_period"] == 1
    assert data["overdue_installments"] == 1

    listed = client.get(f"/api/v1/debts/{debt['id']}/installments").json()
    assert listed[0]["status"] == "overdue"


def test_monthly_close_paid_installment(client) -> None:
    household, _, debt = _scenario(client)
    client.post(
        f"/api/v1/debts/{debt['id']}/installments",
        json={"due_date": "2026-09-20", "principal_amount": 30000},
    )
    account = client.get(f"/api/v1/accounts?household_id={household['id']}").json()[0]
    client.post(
        f"/api/v1/debts/{debt['id']}/payments",
        json={"account_id": account["id"], "amount": 30000, "payment_date": "2026-09-21"},
    )
    response = client.post(
        f"/api/v1/households/{household['id']}/monthly-close", json={"year": 2026, "month": 9}
    )
    assert response.status_code == 200
    listed = client.get(f"/api/v1/debts/{debt['id']}/installments").json()
    assert listed[0]["status"] == "paid"


def test_monthly_close_idempotent(client) -> None:
    household, _, _ = _scenario(client)
    payload = {"year": 2026, "month": 9}
    assert (
        client.post(f"/api/v1/households/{household['id']}/monthly-close", json=payload).status_code
        == 200
    )
    assert (
        client.post(f"/api/v1/households/{household['id']}/monthly-close", json=payload).status_code
        == 422
    )
