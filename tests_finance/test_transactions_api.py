"""API de transacciones y reglas de saldo calculado (CF1-08)."""

import pytest
from fastapi.testclient import TestClient

from cuentafaro.api import create_app
from cuentafaro.db import create_engine_and_session
from cuentafaro.deps import get_session
from cuentafaro.models import Base


@pytest.fixture()
def client(tmp_path):
    engine, session_factory = create_engine_and_session(f"sqlite:///{tmp_path / 'api4.db'}")
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
        json={"name": "Hogar Tx", "timezone": "America/Santiago"},
    ).json()


def _account(client, household_id, name="Cuenta corriente", balance=1000000):
    return client.post(
        "/api/v1/accounts",
        json={
            "household_id": household_id,
            "name": name,
            "type": "checking",
            "balance_reported": balance,
        },
    ).json()


def _expense_category(client, household_id):
    return client.post(
        f"/api/v1/households/{household_id}/categories",
        json={"name": "Compras", "kind": "expense"},
    ).json()


def test_post_expense_decreases_calculated_balance(client) -> None:
    household = _household(client)
    account = _account(client, household["id"])
    response = client.post(
        "/api/v1/transactions",
        json={
            "account_id": account["id"],
            "type": "expense",
            "amount": 15000,
            "date": "2026-09-15",
            "description": "Supermercado",
        },
    )
    assert response.status_code == 201
    assert response.json()["id"].startswith("txn_")

    updated = client.get(f"/api/v1/accounts/{account['id']}").json()
    assert updated["balance_calculated"] == 985000
    assert updated["balance_reported"] == 1000000


def test_post_income_increases_balance(client) -> None:
    household = _household(client)
    account = _account(client, household["id"], balance=50000)
    response = client.post(
        "/api/v1/transactions",
        json={
            "account_id": account["id"],
            "type": "income",
            "amount": 200000,
            "date": "2026-09-15",
        },
    )
    assert response.status_code == 201
    updated = client.get(f"/api/v1/accounts/{account['id']}").json()
    assert updated["balance_calculated"] == 250000


def test_expense_may_drop_balance_below_zero(client) -> None:
    household = _household(client)
    account = _account(client, household["id"], balance=10000)
    response = client.post(
        "/api/v1/transactions",
        json={
            "account_id": account["id"],
            "type": "expense",
            "amount": 20000,
            "date": "2026-09-15",
        },
    )
    assert response.status_code == 201
    updated = client.get(f"/api/v1/accounts/{account['id']}").json()
    assert updated["balance_calculated"] == -10000


def test_transfer_moves_money_between_own_accounts(client) -> None:
    household = _household(client)
    source = _account(client, household["id"], name="Cuenta 1", balance=500000)
    destination = _account(client, household["id"], name="Cuenta 2", balance=100000)
    response = client.post(
        "/api/v1/transactions",
        json={
            "account_id": source["id"],
            "to_account_id": destination["id"],
            "type": "transfer",
            "amount": 80000,
            "date": "2026-09-15",
        },
    )
    assert response.status_code == 201
    assert client.get(f"/api/v1/accounts/{source['id']}").json()["balance_calculated"] == 420000
    assert (
        client.get(f"/api/v1/accounts/{destination['id']}").json()["balance_calculated"] == 180000
    )


def test_transfer_requires_destination(client) -> None:
    household = _household(client)
    account = _account(client, household["id"])
    response = client.post(
        "/api/v1/transactions",
        json={
            "account_id": account["id"],
            "type": "transfer",
            "amount": 5000,
            "date": "2026-09-15",
        },
    )
    assert response.status_code == 422


def test_transfer_rejects_cross_household(client) -> None:
    household = _household(client)
    source = _account(client, household["id"], name="Origen")
    other = client.post(
        "/api/v1/households",
        json={"name": "Otro Hogar", "timezone": "America/Santiago", "status": "paused"},
    ).json()
    destination = _account(client, other["id"], name="Destino")
    response = client.post(
        "/api/v1/transactions",
        json={
            "account_id": source["id"],
            "to_account_id": destination["id"],
            "type": "transfer",
            "amount": 5000,
            "date": "2026-09-15",
        },
    )
    assert response.status_code == 422


def test_category_kind_must_match_type(client) -> None:
    household = _household(client)
    account = _account(client, household["id"])
    income_category = client.post(
        f"/api/v1/households/{household['id']}/categories",
        json={"name": "Sueldo", "kind": "income"},
    ).json()
    response = client.post(
        "/api/v1/transactions",
        json={
            "account_id": account["id"],
            "category_id": income_category["id"],
            "type": "expense",
            "amount": 1000,
            "date": "2026-09-15",
        },
    )
    assert response.status_code == 422


def test_expense_with_matching_category_is_posted(client) -> None:
    household = _household(client)
    account = _account(client, household["id"])
    category = _expense_category(client, household["id"])
    response = client.post(
        "/api/v1/transactions",
        json={
            "account_id": account["id"],
            "category_id": category["id"],
            "type": "expense",
            "amount": 3000,
            "date": "2026-09-15",
        },
    )
    assert response.status_code == 201


def test_void_transaction_reverses_balance(client) -> None:
    household = _household(client)
    account = _account(client, household["id"], balance=50000)
    transaction = client.post(
        "/api/v1/transactions",
        json={
            "account_id": account["id"],
            "type": "expense",
            "amount": 12000,
            "date": "2026-09-15",
        },
    ).json()
    assert client.get(f"/api/v1/accounts/{account['id']}").json()["balance_calculated"] == 38000

    response = client.post(f"/api/v1/transactions/{transaction['id']}/void")
    assert response.status_code == 200
    assert response.json()["status"] == "voided"
    assert client.get(f"/api/v1/accounts/{account['id']}").json()["balance_calculated"] == 50000


def test_double_void_rejected(client) -> None:
    household = _household(client)
    account = _account(client, household["id"])
    transaction = client.post(
        "/api/v1/transactions",
        json={"account_id": account["id"], "type": "expense", "amount": 1000, "date": "2026-09-15"},
    ).json()
    client.post(f"/api/v1/transactions/{transaction['id']}/void")
    assert client.post(f"/api/v1/transactions/{transaction['id']}/void").status_code == 422


def test_list_by_household_and_month(client) -> None:
    household = _household(client)
    account = _account(client, household["id"])
    client.post(
        "/api/v1/transactions",
        json={"account_id": account["id"], "type": "expense", "amount": 1000, "date": "2026-08-31"},
    )
    client.post(
        "/api/v1/transactions",
        json={"account_id": account["id"], "type": "expense", "amount": 2000, "date": "2026-09-01"},
    )
    client.post(
        "/api/v1/transactions",
        json={"account_id": account["id"], "type": "income", "amount": 3000, "date": "2026-09-30"},
    )
    listed = client.get(f"/api/v1/transactions?household_id={household['id']}&year=2026&month=9")
    assert len(listed.json()) == 2


def test_search_transactions_by_description(client) -> None:
    household = _household(client)
    account = _account(client, household["id"])
    client.post(
        "/api/v1/transactions",
        json={
            "account_id": account["id"],
            "type": "expense",
            "amount": 15000,
            "date": "2026-08-10",
            "description": "Supermercado Líder",
        },
    )
    client.post(
        "/api/v1/transactions",
        json={
            "account_id": account["id"],
            "type": "expense",
            "amount": 5000,
            "date": "2026-08-12",
            "description": "farmacia",
        },
    )
    matched = client.get(
        f"/api/v1/transactions?household_id={household['id']}&q=líder"
    ).json()
    assert len(matched) == 1
    assert matched[0]["description"] == "Supermercado Líder"
    none = client.get(
        f"/api/v1/transactions?household_id={household['id']}&q=inexistente"
    ).json()
    assert none == []


def test_get_missing_transaction_returns_404(client) -> None:
    assert client.get("/api/v1/transactions/txn_inexistente").status_code == 404


def test_update_expense_recalculates_balance(client) -> None:
    household = _household(client)
    account = _account(client, household["id"], balance=100000)
    transaction = client.post(
        "/api/v1/transactions",
        json={
            "account_id": account["id"],
            "type": "expense",
            "amount": 12000,
            "date": "2026-09-15",
            "description": "Supermercado",
        },
    ).json()
    assert client.get(f"/api/v1/accounts/{account['id']}").json()["balance_calculated"] == 88000

    response = client.patch(
        f"/api/v1/transactions/{transaction['id']}",
        json={"amount": 5000, "description": "Verdulería"},
    )
    assert response.status_code == 200
    assert response.json()["amount"] == 5000
    assert response.json()["description"] == "Verdulería"
    assert response.json()["status"] == "posted"
    assert client.get(f"/api/v1/accounts/{account['id']}").json()["balance_calculated"] == 95000


def test_update_expense_changes_account_and_type(client) -> None:
    household = _household(client)
    origen = _account(client, household["id"], name="Origen", balance=100000)
    destino = _account(client, household["id"], name="Destino", balance=50000)
    transaction = client.post(
        "/api/v1/transactions",
        json={"account_id": origen["id"], "type": "income", "amount": 20000, "date": "2026-09-15"},
    ).json()
    response = client.patch(
        f"/api/v1/transactions/{transaction['id']}",
        json={
            "account_id": destino["id"],
            "type": "expense",
            "amount": 15000,
            "date": "2026-09-20",
        },
    )
    assert response.status_code == 200
    assert response.json()["account_id"] == destino["id"]
    assert response.json()["type"] == "expense"
    assert client.get(f"/api/v1/accounts/{origen['id']}").json()["balance_calculated"] == 100000
    assert client.get(f"/api/v1/accounts/{destino['id']}").json()["balance_calculated"] == 35000


def test_update_transfer_adjusts_both_accounts(client) -> None:
    household = _household(client)
    source = _account(client, household["id"], name="Cuenta 1", balance=500000)
    destination = _account(client, household["id"], name="Cuenta 2", balance=100000)
    transfer = client.post(
        "/api/v1/transactions",
        json={
            "account_id": source["id"],
            "to_account_id": destination["id"],
            "type": "transfer",
            "amount": 80000,
            "date": "2026-09-15",
        },
    ).json()
    response = client.patch(f"/api/v1/transactions/{transfer['id']}", json={"amount": 30000})
    assert response.status_code == 200
    assert client.get(f"/api/v1/accounts/{source['id']}").json()["balance_calculated"] == 470000
    assert (
        client.get(f"/api/v1/accounts/{destination['id']}").json()["balance_calculated"] == 130000
    )


def test_update_category_kind_mismatch_rejected(client) -> None:
    household = _household(client)
    account = _account(client, household["id"])
    category = _expense_category(client, household["id"])
    transaction = client.post(
        "/api/v1/transactions",
        json={
            "account_id": account["id"],
            "category_id": category["id"],
            "type": "expense",
            "amount": 3000,
            "date": "2026-09-15",
        },
    ).json()
    response = client.patch(
        f"/api/v1/transactions/{transaction['id']}", json={"type": "income"}
    )
    assert response.status_code == 422


def test_update_voided_transaction_rejected(client) -> None:
    household = _household(client)
    account = _account(client, household["id"])
    transaction = client.post(
        "/api/v1/transactions",
        json={"account_id": account["id"], "type": "expense", "amount": 1000, "date": "2026-09-15"},
    ).json()
    client.post(f"/api/v1/transactions/{transaction['id']}/void")
    response = client.patch(f"/api/v1/transactions/{transaction['id']}", json={"amount": 2000})
    assert response.status_code == 422


def test_update_recalculates_budget_actual_amount(client) -> None:
    household = _household(client)
    account = _account(client, household["id"])
    category = _expense_category(client, household["id"])
    budget = client.post(
        f"/api/v1/households/{household['id']}/budgets",
        json={"year": 2026, "month": 9, "status": "draft"},
    ).json()
    client.patch(f"/api/v1/budgets/{budget['id']}", json={"status": "active"})
    client.post(
        f"/api/v1/budgets/{budget['id']}/categories",
        json={"category_id": category["id"], "planned_amount": 100000},
    )
    transaction = client.post(
        "/api/v1/transactions",
        json={
            "account_id": account["id"],
            "category_id": category["id"],
            "type": "expense",
            "amount": 30000,
            "date": "2026-09-15",
        },
    ).json()
    client.patch(f"/api/v1/transactions/{transaction['id']}", json={"amount": 10000})
    rows = client.get(f"/api/v1/budgets/{budget['id']}/categories").json()
    assert rows[0]["category_id"] == category["id"]
    assert rows[0]["actual_amount"] == 10000
