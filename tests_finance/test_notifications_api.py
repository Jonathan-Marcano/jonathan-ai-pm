"""API de avisos programados (Fase 4, CF4-07/CF4-08)."""

from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient

from cuentafaro.api import create_app
from cuentafaro.db import create_engine_and_session
from cuentafaro.deps import get_session
from cuentafaro.models import Base


@pytest.fixture()
def client(tmp_path):
    engine, session_factory = create_engine_and_session(f"sqlite:///{tmp_path / 'ntf_api.db'}")
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
        json={"name": "Hogar API", "timezone": "America/Santiago"},
    ).json()


def _account(client, household_id):
    client.post(
        "/api/v1/accounts",
        json={
            "household_id": household_id,
            "name": "Cta",
            "type": "checking",
            "balance_reported": 1_000_000,
        },
    )


def _debt(client, household_id):
    return client.post(
        f"/api/v1/households/{household_id}/debts",
        json={
            "name": "Auto",
            "type": "loan",
            "original_amount": 300_000,
            "minimum_payment": 20_000,
            "due_day": 5,
        },
    ).json()


def test_preferences_have_defaults_and_can_toggle(client) -> None:
    household = _household(client)
    response = client.get(f"/api/v1/households/{household['id']}/notification-preferences")
    assert response.status_code == 200
    prefs = response.json()
    assert {p["template_kind"] for p in prefs} == {
        "upcoming_payment",
        "weekly_summary",
        "budget_deviation",
        "monthly_close",
    }
    assert all(p["enabled"] for p in prefs)

    patched = client.patch(
        f"/api/v1/households/{household['id']}/notification-preferences",
        json={"template_kind": "weekly_summary", "enabled": False},
    )
    assert patched.status_code == 200
    toggled = {p["template_kind"]: p["enabled"] for p in patched.json()}
    assert toggled["weekly_summary"] is False
    assert toggled["upcoming_payment"] is True

    again = client.get(f"/api/v1/households/{household['id']}/notification-preferences").json()
    assert {p["template_kind"]: p["enabled"] for p in again}["weekly_summary"] is False


def test_preference_unknown_kind_rejected(client) -> None:
    household = _household(client)
    response = client.patch(
        f"/api/v1/households/{household['id']}/notification-preferences",
        json={"template_kind": "spam", "enabled": True},
    )
    assert response.status_code == 422


def test_run_endpoint_enqueues_sends_and_lists(client) -> None:
    household = _household(client)
    _account(client, household["id"])
    debt = _debt(client, household["id"])
    due = date.today() + timedelta(days=1)
    client.post(
        f"/api/v1/debts/{debt['id']}/installments",
        json={"due_date": due.isoformat(), "principal_amount": 30_000},
    )

    result = client.post(f"/api/v1/households/{household['id']}/notifications/run")
    assert result.status_code == 200
    body = result.json()
    assert body["enqueued"] == 1
    assert body["sent"] == 1
    assert body["failed"] == 0

    notifications = client.get(f"/api/v1/households/{household['id']}/notifications").json()
    assert len(notifications) == 1
    assert notifications[0]["status"] == "sent"
    assert notifications[0]["template_kind"] == "upcoming_payment"
    assert notifications[0]["send_provider"] == "simulated"
    assert notifications[0]["message_id"]

    sends = client.get(f"/api/v1/households/{household['id']}/notifications/sends").json()
    assert len(sends) == 1
    assert sends[0]["provider"] == "simulated"
    assert sends[0]["title"] == "Pago próximo por vencer"

    second = client.post(f"/api/v1/households/{household['id']}/notifications/run").json()
    assert second["enqueued"] == 0  # idempotente por external_ref


def test_notifications_are_isolated_by_household(client) -> None:
    first = _household(client)
    second = client.post(
        "/api/v1/households",
        json={"name": "Otro hogar", "timezone": "America/Santiago", "status": "archived"},
    ).json()
    _account(client, first["id"])
    debt = _debt(client, first["id"])
    due = date.today() + timedelta(days=1)
    client.post(
        f"/api/v1/debts/{debt['id']}/installments",
        json={"due_date": due.isoformat(), "principal_amount": 30_000},
    )
    client.post(f"/api/v1/households/{first['id']}/notifications/run")

    assert len(client.get(f"/api/v1/households/{first['id']}/notifications").json()) == 1
    assert len(client.get(f"/api/v1/households/{second['id']}/notifications").json()) == 0
    assert len(client.get(f"/api/v1/households/{second['id']}/notifications/sends").json()) == 0
