"""API de instituciones financieras y cuentas (CF1-04, CF1-05)."""

import pytest
from fastapi.testclient import TestClient

from cuentafaro.api import create_app
from cuentafaro.db import create_engine_and_session
from cuentafaro.deps import get_session
from cuentafaro.models import Base


@pytest.fixture()
def client(tmp_path):
    engine, session_factory = create_engine_and_session(f"sqlite:///{tmp_path / 'api2.db'}")
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
        json={"name": "Hogar A", "timezone": "America/Santiago"},
    ).json()


def test_create_institution(client) -> None:
    response = client.post(
        "/api/v1/financial-institutions",
        json={"name": "Banco Futuro", "type": "bank", "status": "active"},
    )
    assert response.status_code == 201
    assert response.json()["id"].startswith("fin_")
    assert response.json()["type"] == "bank"


def test_institution_name_unique_conflict(client) -> None:
    payload = {"name": "Banco Único", "type": "bank"}
    assert client.post("/api/v1/financial-institutions", json=payload).status_code == 201
    response = client.post("/api/v1/financial-institutions", json=payload)
    assert response.status_code == 409


def test_list_and_update_institution(client) -> None:
    institution = client.post(
        "/api/v1/financial-institutions", json={"name": "Fintech X", "type": "fintech"}
    ).json()
    listed = client.get("/api/v1/financial-institutions")
    assert len(listed.json()) == 1

    updated = client.patch(
        f"/api/v1/financial-institutions/{institution['id']}",
        json={"name": "Fintech X Renombrada"},
    )
    assert updated.status_code == 200
    assert updated.json()["name"] == "Fintech X Renombrada"


def test_delete_institution_nulls_account_reference(client) -> None:
    household = _household(client)
    institution = client.post(
        "/api/v1/financial-institutions", json={"name": "Banco Borrado", "type": "bank"}
    ).json()
    account = client.post(
        "/api/v1/accounts",
        json={
            "household_id": household["id"],
            "institution_id": institution["id"],
            "name": "Cuenta",
            "type": "checking",
        },
    ).json()
    assert account["institution_id"] == institution["id"]

    response = client.delete(f"/api/v1/financial-institutions/{institution['id']}")
    assert response.status_code == 204
    assert client.get("/api/v1/financial-institutions").json() == []
    detached = client.get(f"/api/v1/accounts/{account['id']}").json()
    assert detached["institution_id"] is None


def test_delete_missing_institution_returns_404(client) -> None:
    assert client.delete("/api/v1/financial-institutions/fin_inexistente").status_code == 404


def test_create_account(client) -> None:
    household = _household(client)
    institution = client.post(
        "/api/v1/financial-institutions", json={"name": "Banco A", "type": "bank"}
    ).json()
    response = client.post(
        "/api/v1/accounts",
        json={
            "household_id": household["id"],
            "institution_id": institution["id"],
            "name": "Cuenta corriente",
            "type": "checking",
            "currency": "CLP",
            "balance_reported": 850000,
            "status": "active",
        },
    )
    assert response.status_code == 201
    account = response.json()
    assert account["id"].startswith("fac_")
    assert account["balance_reported"] == 850000
    assert account["balance_calculated"] == 850000
    assert isinstance(account["balance_reported"], int)


def test_create_account_without_institution(client) -> None:
    household = _household(client)
    response = client.post(
        "/api/v1/accounts",
        json={"household_id": household["id"], "name": "Efectivo", "type": "cash"},
    )
    assert response.status_code == 201
    assert response.json()["institution_id"] is None


def test_account_rejects_missing_household(client) -> None:
    response = client.post(
        "/api/v1/accounts",
        json={"household_id": "hh_inexistente", "name": "Cuenta", "type": "checking"},
    )
    assert response.status_code == 404


def test_create_credit_card_with_credit_limit(client) -> None:
    household = _household(client)
    institution = client.post(
        "/api/v1/financial-institutions", json={"name": "Banco Cupo", "type": "bank"}
    ).json()
    response = client.post(
        "/api/v1/accounts",
        json={
            "household_id": household["id"],
            "institution_id": institution["id"],
            "name": "Visa Oro",
            "type": "credit_card",
            "balance_reported": 350000,
            "credit_limit": 1000000,
        },
    )
    assert response.status_code == 201
    account = response.json()
    assert account["credit_limit"] == 1000000
    assert account["institution_name"] == "Banco Cupo"


def test_update_account_credit_limit(client) -> None:
    household = _household(client)
    account = client.post(
        "/api/v1/accounts",
        json={
            "household_id": household["id"],
            "name": "Tarjeta",
            "type": "credit_card",
            "credit_limit": 500000,
        },
    ).json()
    assert account["credit_limit"] == 500000
    response = client.patch(f"/api/v1/accounts/{account['id']}", json={"credit_limit": 800000})
    assert response.status_code == 200
    assert response.json()["credit_limit"] == 800000


def test_account_rejects_negative_credit_limit(client) -> None:
    household = _household(client)
    response = client.post(
        "/api/v1/accounts",
        json={
            "household_id": household["id"],
            "name": "Tarjeta",
            "type": "credit_card",
            "credit_limit": -100,
        },
    )
    assert response.status_code == 422


def test_create_card_with_statement_and_due_day(client) -> None:
    household = _household(client)
    response = client.post(
        "/api/v1/accounts",
        json={
            "household_id": household["id"],
            "name": "Visa Cierre",
            "type": "credit_card",
            "balance_reported": 200000,
            "credit_limit": 1000000,
            "statement_day": 5,
            "due_day": 20,
        },
    )
    assert response.status_code == 201
    account = response.json()
    assert account["statement_day"] == 5
    assert account["due_day"] == 20


def test_update_card_statement_and_due_day(client) -> None:
    household = _household(client)
    account = client.post(
        "/api/v1/accounts",
        json={
            "household_id": household["id"],
            "name": "Visa Editable",
            "type": "credit_card",
        },
    ).json()
    response = client.patch(
        f"/api/v1/accounts/{account['id']}",
        json={"statement_day": 1, "due_day": 15},
    )
    assert response.status_code == 200
    updated = response.json()
    assert updated["statement_day"] == 1
    assert updated["due_day"] == 15


def test_account_rejects_out_of_range_days(client) -> None:
    household = _household(client)
    for payload in (
        {"statement_day": 0},
        {"statement_day": 32},
        {"due_day": 32},
    ):
        response = client.post(
            "/api/v1/accounts",
            json={"household_id": household["id"], "name": f"T {payload}", **payload},
        )
        assert response.status_code == 422


def test_plain_account_has_null_days(client) -> None:
    household = _household(client)
    account = client.post(
        "/api/v1/accounts",
        json={"household_id": household["id"], "name": "Corriente", "type": "checking"},
    ).json()
    assert account["statement_day"] is None
    assert account["due_day"] is None


def test_list_accounts_includes_institution_name(client) -> None:
    household = _household(client)
    institution = client.post(
        "/api/v1/financial-institutions", json={"name": "Fintech Lista", "type": "fintech"}
    ).json()
    client.post(
        "/api/v1/accounts",
        json={
            "household_id": household["id"],
            "institution_id": institution["id"],
            "name": "Cuenta",
            "type": "checking",
        },
    ).json()
    listed = client.get(f"/api/v1/accounts?household_id={household['id']}").json()
    assert listed[0]["institution_name"] == "Fintech Lista"


def test_credit_card_without_credit_limit_is_null(client) -> None:
    household = _household(client)
    account = client.post(
        "/api/v1/accounts",
        json={"household_id": household["id"], "name": "Tarjeta Básica", "type": "credit_card"},
    ).json()
    assert account["credit_limit"] is None
    assert account["institution_name"] is None


def test_account_allows_negative_balances(client) -> None:
    household = _household(client)
    response = client.post(
        "/api/v1/accounts",
        json={
            "household_id": household["id"],
            "name": "Cuenta",
            "type": "checking",
            "balance_reported": -100,
        },
    )
    assert response.status_code == 201
    assert response.json()["balance_reported"] == -100
    assert response.json()["balance_calculated"] == -100


def test_list_accounts_by_household(client) -> None:
    household = _household(client)
    client.post(
        "/api/v1/accounts",
        json={"household_id": household["id"], "name": "Cuenta 1", "type": "checking"},
    )
    client.post(
        "/api/v1/accounts",
        json={"household_id": household["id"], "name": "Cuenta 2", "type": "savings"},
    )
    listed = client.get(f"/api/v1/accounts?household_id={household['id']}")
    assert len(listed.json()) == 2


def test_update_account_reports_reported_balance(client) -> None:
    household = _household(client)
    account = client.post(
        "/api/v1/accounts",
        json={"household_id": household["id"], "name": "Cuenta", "type": "checking"},
    ).json()
    response = client.patch(f"/api/v1/accounts/{account['id']}", json={"balance_reported": 920000})
    assert response.status_code == 200
    assert response.json()["balance_reported"] == 920000


def test_get_missing_account_returns_404(client) -> None:
    assert client.get("/api/v1/accounts/fac_inexistente").status_code == 404
