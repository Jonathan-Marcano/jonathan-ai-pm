"""API de deudas, cuotas y pagos de deuda (CF1-09, CF1-10, CF1-11)."""

import pytest
from fastapi.testclient import TestClient

from cuentafaro.api import create_app
from cuentafaro.db import create_engine_and_session
from cuentafaro.deps import get_session
from cuentafaro.models import Base


@pytest.fixture()
def client(tmp_path):
    engine, session_factory = create_engine_and_session(f"sqlite:///{tmp_path / 'api5.db'}")
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
        json={"name": "Hogar Deudas", "timezone": "America/Santiago"},
    ).json()


def _account(client, household_id, balance=1500000):
    return client.post(
        "/api/v1/accounts",
        json={
            "household_id": household_id,
            "name": "Cuenta corriente",
            "type": "checking",
            "balance_reported": balance,
        },
    ).json()


def _debt(client, household_id, **overrides):
    payload = {
        "name": "Tarjeta ABC",
        "type": "credit_card",
        "original_amount": 800000,
        "minimum_payment": 50000,
        "interest_rate": 2.5,
        "due_day": 10,
    }
    payload.update(**overrides)
    response = client.post(f"/api/v1/households/{household_id}/debts", json=payload)
    assert response.status_code == 201
    return response.json()


def test_create_debt_sets_balance_to_original(client) -> None:
    household = _household(client)
    debt = _debt(client, household["id"])
    assert debt["id"].startswith("dbt_")
    assert debt["current_balance"] == 800000
    assert debt["original_amount"] == 800000
    assert isinstance(debt["current_balance"], int)


def test_debt_rejects_invalid_due_day(client) -> None:
    household = _household(client)
    response = client.post(
        f"/api/v1/households/{household['id']}/debts",
        json={"name": "Prestamo", "type": "loan", "original_amount": 100000, "due_day": 32},
    )
    assert response.status_code == 422


def test_list_and_get_debt(client) -> None:
    household = _household(client)
    debt = _debt(client, household["id"])
    listed = client.get(f"/api/v1/households/{household['id']}/debts")
    assert len(listed.json()) == 1
    fetched = client.get(f"/api/v1/debts/{debt['id']}")
    assert fetched.status_code == 200
    assert fetched.json()["name"] == "Tarjeta ABC"


def test_update_debt(client) -> None:
    household = _household(client)
    debt = _debt(client, household["id"])
    response = client.patch(f"/api/v1/debts/{debt['id']}", json={"minimum_payment": 75000})
    assert response.status_code == 200
    assert response.json()["minimum_payment"] == 75000


def test_pay_debt_reduces_balance_and_account(client) -> None:
    household = _household(client)
    account = _account(client, household["id"])
    debt = _debt(client, household["id"], account_id=account["id"])
    response = client.post(
        f"/api/v1/debts/{debt['id']}/payments",
        json={
            "account_id": account["id"],
            "amount": 60000,
            "type": "ordinary",
            "payment_date": "2026-09-15",
        },
    )
    assert response.status_code == 201
    payment = response.json()
    assert payment["id"].startswith("dpay_")
    assert payment["transaction_id"].startswith("txn_")

    updated_debt = client.get(f"/api/v1/debts/{debt['id']}").json()
    assert updated_debt["current_balance"] == 740000
    assert client.get(f"/api/v1/accounts/{account['id']}").json()["balance_calculated"] == 1440000


def test_payment_can_be_without_account(client) -> None:
    household = _household(client)
    debt = _debt(client, household["id"])
    response = client.post(
        f"/api/v1/debts/{debt['id']}/payments",
        json={"amount": 30000, "payment_date": "2026-09-15", "type": "extraordinary"},
    )
    assert response.status_code == 201
    assert response.json()["transaction_id"] is None
    assert client.get(f"/api/v1/debts/{debt['id']}").json()["current_balance"] == 770000


def test_payment_cannot_exceed_balance(client) -> None:
    household = _household(client)
    debt = _debt(client, household["id"], original_amount=100000)
    response = client.post(
        f"/api/v1/debts/{debt['id']}/payments",
        json={"amount": 200000, "payment_date": "2026-09-15"},
    )
    assert response.status_code == 422


def test_payment_liquidating_debt_marks_paid_off(client) -> None:
    household = _household(client)
    debt = _debt(client, household["id"], original_amount=100000)
    response = client.post(
        f"/api/v1/debts/{debt['id']}/payments",
        json={"amount": 100000, "payment_date": "2026-09-15"},
    )
    assert response.status_code == 201
    updated = client.get(f"/api/v1/debts/{debt['id']}").json()
    assert updated["current_balance"] == 0
    assert updated["status"] == "paid_off"
    assert (
        client.post(
            f"/api/v1/debts/{debt['id']}/payments",
            json={"amount": 1000, "payment_date": "2026-09-16"},
        ).status_code
        == 422
    )


def test_create_installment(client) -> None:
    household = _household(client)
    debt = _debt(client, household["id"])
    response = client.post(
        f"/api/v1/debts/{debt['id']}/installments",
        json={
            "due_date": "2026-12-10",
            "principal_amount": 80000,
            "interest_amount": 20000,
            "fee_amount": 1000,
        },
    )
    assert response.status_code == 201
    installment = response.json()
    assert installment["id"].startswith("ins_")
    assert installment["total_amount"] == 101000
    assert installment["status"] == "pending"


def test_list_and_update_installment(client) -> None:
    household = _household(client)
    debt = _debt(client, household["id"])
    installment = client.post(
        f"/api/v1/debts/{debt['id']}/installments",
        json={"due_date": "2026-12-10", "principal_amount": 50000},
    ).json()
    listed = client.get(f"/api/v1/debts/{debt['id']}/installments")
    assert len(listed.json()) == 1
    response = client.patch(f"/api/v1/installments/{installment['id']}", json={"status": "paid"})
    assert response.status_code == 200
    assert response.json()["status"] == "paid"


def test_debt_payments_require_active_debt(client) -> None:
    household = _household(client)
    debt = _debt(client, household["id"])
    client.patch(f"/api/v1/debts/{debt['id']}", json={"status": "closed"})
    response = client.post(
        f"/api/v1/debts/{debt['id']}/payments",
        json={"amount": 1000, "payment_date": "2026-09-15"},
    )
    assert response.status_code == 422
