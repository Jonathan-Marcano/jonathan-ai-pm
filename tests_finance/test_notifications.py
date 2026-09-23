"""Plantillas y programador de avisos (Fase 4, CF4-06/CF4-07).

El programador es por fecha e idempotente: misma fecha → misma cola de salida
y un solo envío por aviso. Las plantillas son deterministas.
"""

from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient

from cuentafaro.api import create_app
from cuentafaro.db import create_engine_and_session
from cuentafaro.deps import get_session
from cuentafaro.messaging import get_messaging_provider
from cuentafaro.models import Base, Notification, NotificationSend
from cuentafaro.notifications import (
    render_budget_deviation,
    render_monthly_close,
    render_upcoming_payment,
    render_weekly_summary,
)
from cuentafaro.notifications.scheduler import run_household_notifications
from cuentafaro.services import DomainStore


@pytest.fixture()
def client(tmp_path):
    engine, session_factory = create_engine_and_session(f"sqlite:///{tmp_path / 'ntf.db'}")
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
        yield test_client, session_factory
    app.dependency_overrides.clear()
    engine.dispose()


def _household(client):
    return client.post(
        "/api/v1/households",
        json={"name": "Hogar Avisos", "timezone": "America/Santiago"},
    ).json()


def _account(client, household_id):
    return client.post(
        "/api/v1/accounts",
        json={
            "household_id": household_id,
            "name": "Cta",
            "type": "checking",
            "balance_reported": 1_000_000,
        },
    ).json()


def _debt(client, household_id, due_day=10):
    response = client.post(
        f"/api/v1/households/{household_id}/debts",
        json={
            "name": "Tarjeta",
            "type": "credit_card",
            "original_amount": 500_000,
            "minimum_payment": 25_000,
            "due_day": due_day,
        },
    )
    assert response.status_code == 201
    return response.json()


def _installment(client, debt_id, due_date, amount=45_000):
    return client.post(
        f"/api/v1/debts/{debt_id}/installments",
        json={"due_date": due_date.isoformat(), "principal_amount": amount},
    ).json()


def _run(client, session_factory, household_id, today):
    session = session_factory()
    try:
        return run_household_notifications(
            session, get_messaging_provider(), household_id, today=today
        )
    finally:
        session.close()


# ---------- Plantillas (CF4-06) ----------


def test_upcoming_payment_template_formats_amount() -> None:
    title, body = render_upcoming_payment(
        debt_name="Tarjeta", amount=45_890, due_date=date(2026, 9, 22), days_left=1
    )
    assert title == "Pago próximo por vencer"
    assert "Tarjeta vence el 2026-09-22 (en 1 día): $45.890." in body


def test_weekly_summary_template_reports_period() -> None:
    title, body = render_weekly_summary(
        week_start=date(2026, 9, 14),
        week_end=date(2026, 9, 20),
        income=200_000,
        expenses=150_000,
        balance=50_000,
    )
    assert "Resumen 2026-09-14 → 2026-09-20" in body
    assert "Ingresos: $200.000" in body
    assert "Balance: $50.000" in body


def test_budget_deviation_template_lists_over_budget_rows() -> None:
    title, body = render_budget_deviation(
        [{"category_name": "Vivienda", "planned": 100_000, "actual": 150_000}]
    )
    assert title == "Desviación frente al presupuesto"
    assert "$150.000 vs $100.000" in body


def test_monthly_close_template_invites_to_cut_period() -> None:
    title, body = render_monthly_close(period="2026-09", expenses=800_000, budget_total=1_000_000)
    assert title == "Solicitud de cierre de mes"
    assert "Cierre el período 2026-09" in body
    assert "Gastos del mes: $800.000" in body


# ---------- Programador (CF4-07) ----------


def test_installment_due_enqueued_and_sent(client) -> None:
    test_client, session_factory = client
    household = _household(test_client)
    _account(test_client, household["id"])
    debt = _debt(test_client, household["id"])
    today = date(2026, 9, 21)
    _installment(test_client, debt["id"], today + timedelta(days=1))

    result = _run(test_client, session_factory, household["id"], today)
    assert result["enqueued"] == 1
    assert result["sent"] == 1
    assert result["failed"] == 0

    session = session_factory()
    try:
        notification = session.query(Notification).one()
        assert notification.status == "sent"
        assert notification.template_kind == "upcoming_payment"
        assert notification.send_provider == "simulated"
        assert notification.message_id
        assert "Tarjeta" in notification.body
        assert notification.recipient == "Hogar Avisos"
        sends = session.query(NotificationSend).all()
        assert len(sends) == 1
        assert sends[0].provider == "simulated"
        assert sends[0].title == notification.title
    finally:
        session.close()


def test_run_is_idempotent_by_external_ref(client) -> None:
    test_client, session_factory = client
    household = _household(test_client)
    _account(test_client, household["id"])
    debt = _debt(test_client, household["id"])
    today = date(2026, 9, 21)
    _installment(test_client, debt["id"], today + timedelta(days=1))

    first = _run(test_client, session_factory, household["id"], today)
    second = _run(test_client, session_factory, household["id"], today)
    assert first["enqueued"] == 1
    assert second["enqueued"] == 0  # mismo instalment → sin duplicado

    session = session_factory()
    try:
        assert session.query(Notification).count() == 1
        assert session.query(NotificationSend).count() == 1
    finally:
        session.close()


def test_recurring_minimum_enqueued_when_due_in_horizon(client) -> None:
    test_client, session_factory = client
    household = _household(test_client)
    _account(test_client, household["id"])
    today = date(2026, 9, 21)
    _debt(test_client, household["id"], due_day=today.day)  # mínimo hoy

    result = _run(test_client, session_factory, household["id"], today)
    assert result["enqueued"] == 1
    assert result["sent"] == 1


def test_weekly_summary_only_on_sunday(client) -> None:
    test_client, session_factory = client
    household = _household(test_client)
    account = _account(test_client, household["id"])
    category = test_client.get(f"/api/v1/households/{household['id']}/categories").json()[0]

    sunday = date(2026, 9, 20)
    test_client.post(
        "/api/v1/transactions",
        json={
            "account_id": account["id"],
            "type": "income",
            "amount": 200_000,
            "date": "2026-09-15",
        },
    )
    test_client.post(
        "/api/v1/transactions",
        json={
            "account_id": account["id"],
            "category_id": category["id"],
            "type": "expense",
            "amount": 80_000,
            "date": "2026-09-16",
        },
    )

    monday = date(2026, 9, 21)
    result_off = _run(test_client, session_factory, household["id"], monday)
    assert result_off["enqueued"] == 0
    assert _kinds(test_client, session_factory, household["id"]) == set()

    result_on = _run(test_client, session_factory, household["id"], sunday)
    assert result_on["enqueued"] == 1

    session = session_factory()
    try:
        notification = session.query(Notification).filter_by(template_kind="weekly_summary").one()
        assert "Ingresos: $200.000" in notification.body
        assert "Gastos: $80.000" in notification.body
    finally:
        session.close()


def test_budget_deviation_when_actual_exceeds_planned(client) -> None:
    test_client, session_factory = client
    household = _household(test_client)
    account = _account(test_client, household["id"])
    category = test_client.post(
        f"/api/v1/households/{household['id']}/categories",
        json={"name": "Compras", "kind": "expense"},
    ).json()
    budget = test_client.post(
        f"/api/v1/households/{household['id']}/budgets",
        json={"year": 2026, "month": 9, "status": "active"},
    ).json()
    test_client.post(
        f"/api/v1/budgets/{budget['id']}/categories",
        json={"category_id": category["id"], "planned_amount": 50_000},
    )
    test_client.post(
        "/api/v1/transactions",
        json={
            "account_id": account["id"],
            "category_id": category["id"],
            "type": "expense",
            "amount": 60_000,
            "date": "2026-09-10",
        },
    )

    today = date(2026, 9, 28)
    result = _run(test_client, session_factory, household["id"], today)
    assert result["enqueued"] == 2  # desviación + cierre de mes

    session = session_factory()
    try:
        notification = session.query(Notification).filter_by(template_kind="budget_deviation").one()
        assert "Compras" in notification.body
    finally:
        session.close()


def test_monthly_close_request_from_day_28(client) -> None:
    test_client, session_factory = client
    household = _household(test_client)
    _account(test_client, household["id"])

    before = date(2026, 9, 25)  # viernes: sin avisos por fecha
    assert _run(test_client, session_factory, household["id"], before)["enqueued"] == 0

    today = date(2026, 9, 28)  # lunes, fin de mes
    result = _run(test_client, session_factory, household["id"], today)
    assert result["enqueued"] == 1

    session = session_factory()
    try:
        notification = session.query(Notification).filter_by(template_kind="monthly_close").one()
        assert "2026-09" in notification.body
    finally:
        session.close()


def test_disabled_preference_blocks_enqueue(client) -> None:
    test_client, session_factory = client
    household = _household(test_client)
    _account(test_client, household["id"])
    debt = _debt(test_client, household["id"])
    today = date(2026, 9, 21)
    _installment(test_client, debt["id"], today + timedelta(days=1))

    test_client.patch(
        f"/api/v1/households/{household['id']}/notification-preferences",
        json={"template_kind": "upcoming_payment", "enabled": False},
    )
    result = _run(test_client, session_factory, household["id"], today)
    assert result["enqueued"] == 0


def _kinds(test_client, session_factory, household_id) -> set[str]:
    session = session_factory()
    try:
        store = DomainStore(session)
        kinds = set()
        for row in store.list_notifications(household_id):
            kinds.add(row.template_kind)
        return kinds
    finally:
        session.close()
