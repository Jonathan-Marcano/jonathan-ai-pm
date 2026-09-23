"""Estrategias de pago y escenarios con ingresos extraordinarios (CF1-18, CF1-19)."""

import pytest
from fastapi.testclient import TestClient

from cuentafaro.api import create_app
from cuentafaro.db import create_engine_and_session
from cuentafaro.deps import get_session
from cuentafaro.models import Base


@pytest.fixture()
def client(tmp_path):
    engine, session_factory = create_engine_and_session(f"sqlite:///{tmp_path / 'api8.db'}")
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
        json={"name": "Hogar Proyección", "timezone": "America/Santiago"},
    ).json()


def _debt(client, household_id, name, original, rate, minimum):
    return client.post(
        f"/api/v1/households/{household_id}/debts",
        json={
            "name": name,
            "type": "credit_card" if "Tarjeta" in name else "loan",
            "original_amount": original,
            "interest_rate": rate,
            "minimum_payment": minimum,
            "due_day": 10,
        },
    ).json()


def test_snowball_orders_by_smallest_balance(client) -> None:
    household = _household(client)
    big = _debt(client, household["id"], "Préstamo grande", 900000, 3.0, 40000)
    small = _debt(client, household["id"], "Tarjeta chica", 200000, 5.0, 15000)
    data = client.post(
        f"/api/v1/households/{household['id']}/projections/simulate",
        json={"strategy": "snowball", "monthly_payment": 200000},
    ).json()
    assert data["converged"] is True
    order = [item["debt_id"] for item in data["payoff_order"]]
    assert order == [small["id"], big["id"]]


def test_avalanche_orders_by_highest_rate(client) -> None:
    household = _household(client)
    low = _debt(client, household["id"], "Préstamo bajo", 900000, 1.0, 40000)
    dog = _debt(client, household["id"], "Tarjeta cara", 300000, 6.0, 15000)
    data = client.post(
        f"/api/v1/households/{household['id']}/projections/simulate",
        json={"strategy": "avalanche", "monthly_payment": 200000},
    ).json()
    order = [item["debt_id"] for item in data["payoff_order"]]
    assert order == [dog["id"], low["id"]]


def test_simulation_reports_months_and_paid(client) -> None:
    household = _household(client)
    _debt(client, household["id"], "Tarjeta única", 300000, 2.0, 20000)
    data = client.post(
        f"/api/v1/households/{household['id']}/projections/simulate",
        json={"strategy": "snowball", "monthly_payment": 150000},
    ).json()
    assert data["converged"] is True
    assert data["months_to_freedom"] >= 2
    assert isinstance(data["total_interest"], int)
    assert data["total_paid"] >= 300000


def test_simulation_exposes_monthly_balance_series(client) -> None:
    household = _household(client)
    _debt(client, household["id"], "Tarjeta única", 300000, 2.0, 20000)
    data = client.post(
        f"/api/v1/households/{household['id']}/projections/simulate",
        json={"strategy": "snowball", "monthly_payment": 150000},
    ).json()
    series = data["months_series"]
    assert isinstance(series, list) and len(series) >= 2
    assert series[0]["month"] == 1
    assert series[0]["balance"] <= 320000
    assert series[-1]["balance"] == 0
    assert series[-1]["interest"] == data["total_interest"]
    balances = [point["balance"] for point in series]
    assert balances == sorted(balances, reverse=True)


def test_payoff_order_includes_balance_and_rate(client) -> None:
    household = _household(client)
    debt = _debt(client, household["id"], "Tarjeta única", 300000, 2.0, 20000)
    data = client.post(
        f"/api/v1/households/{household['id']}/projections/simulate",
        json={"strategy": "snowball", "monthly_payment": 150000},
    ).json()
    entry = data["payoff_order"][0]
    assert entry["debt_id"] == debt["id"]
    assert entry["name"] == "Tarjeta única"
    assert entry["current_balance"] == 300000
    assert entry["interest_rate"] == 2.0
    assert entry["minimum_payment"] == 20000


def test_low_payment_may_not_converge(client) -> None:
    household = _household(client)
    _debt(client, household["id"], "Deuda grande", 5000000, 5.0, 250000)
    data = client.post(
        f"/api/v1/households/{household['id']}/projections/simulate",
        json={"strategy": "snowball", "monthly_payment": 10000},
    ).json()
    assert data["converged"] is False
    assert data["months_to_freedom"] is None


def test_simulation_requires_active_debts(client) -> None:
    household = _household(client)
    response = client.post(
        f"/api/v1/households/{household['id']}/projections/simulate",
        json={"strategy": "snowball", "monthly_payment": 100000},
    )
    assert response.status_code == 422


def test_create_plan_and_select_status(client) -> None:
    household = _household(client)
    plan = client.post(
        f"/api/v1/households/{household['id']}/plans",
        json={"strategy": "avalanche", "name": "Plan avalancha"},
    ).json()
    assert plan["id"].startswith("pln_")
    assert plan["status"] == "draft"
    updated = client.patch(f"/api/v1/plans/{plan['id']}", json={"status": "selected"})
    assert updated.status_code == 200
    assert updated.json()["status"] == "selected"


def test_run_scenario_requires_active_debts(client) -> None:
    household = _household(client)
    plan = client.post(
        f"/api/v1/households/{household['id']}/plans",
        json={"strategy": "snowball", "name": "Plan sin deudas"},
    ).json()
    response = client.post(
        f"/api/v1/plans/{plan['id']}/scenarios",
        json={"name": "Sin deudas", "monthly_payment": 100000},
    )
    assert response.status_code == 422
    assert "No hay deudas activas para simular" in response.json()["detail"]


def test_run_scenario_stores_income_and_result(client) -> None:
    household = _household(client)
    _debt(client, household["id"], "Tarjeta X", 600000, 3.0, 30000)
    plan = client.post(
        f"/api/v1/households/{household['id']}/plans",
        json={"strategy": "snowball", "name": "Plan base"},
    ).json()
    response = client.post(
        f"/api/v1/plans/{plan['id']}/scenarios",
        json={
            "name": "Con bono de vacaciones",
            "monthly_payment": 150000,
            "extra_income": [{"month_offset": 3, "amount": 250000}],
        },
    )
    assert response.status_code == 201
    scenario = response.json()
    assert scenario["id"].startswith("sce_")
    assert scenario["result_summary"]["converged"] is True
    assert scenario["result_summary"]["months_to_freedom"] >= 2
    assert scenario["result_summary"]["payoff_order"][0]["debt_id"]
    assert scenario["result_summary"]["payoff_order"][0]["current_balance"] == 600000
    assert scenario["extra_income"] == [{"month_offset": 3, "amount": 250000}]
    assert scenario["assumptions"]["note"].startswith("la simulación no modifica")


def test_extra_income_reduces_payoff_time(client) -> None:
    household = _household(client)
    _debt(client, household["id"], "Tarjeta Y", 900000, 3.0, 40000)
    plan = client.post(
        f"/api/v1/households/{household['id']}/plans",
        json={"strategy": "snowball", "name": "Plan"},
    ).json()
    base = client.post(
        f"/api/v1/plans/{plan['id']}/scenarios",
        json={"name": "Sin bono", "monthly_payment": 180000},
    ).json()["result_summary"]["months_to_freedom"]
    with_bonus = client.post(
        f"/api/v1/plans/{plan['id']}/scenarios",
        json={
            "name": "Con bono",
            "monthly_payment": 180000,
            "extra_income": [{"month_offset": 2, "amount": 800000}],
        },
    ).json()["result_summary"]["months_to_freedom"]
    assert with_bonus < base


def test_list_scenarios(client) -> None:
    household = _household(client)
    _debt(client, household["id"], "Tarjeta Z", 400000, 2.0, 20000)
    plan = client.post(
        f"/api/v1/households/{household['id']}/plans",
        json={"strategy": "snowball", "name": "Plan"},
    ).json()
    client.post(
        f"/api/v1/plans/{plan['id']}/scenarios",
        json={"name": "A", "monthly_payment": 100000},
    )
    client.post(
        f"/api/v1/plans/{plan['id']}/scenarios",
        json={"name": "B", "monthly_payment": 200000},
    )
    listed = client.get(f"/api/v1/plans/{plan['id']}/scenarios")
    assert len(listed.json()) == 2
