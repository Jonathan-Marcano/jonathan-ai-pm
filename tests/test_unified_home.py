"""Módulo unificado: hábitos, bandeja y página de inicio (Mi día)."""

from datetime import date

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from cuentafaro.db import create_engine_and_session
from cuentafaro.deps import get_session as get_finance_session
from cuentafaro.models import Base as FinanceBase
from faroflow.api import app
from faroflow.db import build_engine, get_session
from faroflow.models import Base as WorkBase


@pytest.fixture
def api(monkeypatch, tmp_path_factory) -> TestClient:
    db_dir = tmp_path_factory.mktemp("unified_test")
    work_engine = build_engine(f"sqlite:///{db_dir}/work.db")
    WorkBase.metadata.create_all(work_engine)
    finance_engine, finance_factory = create_engine_and_session(
        f"sqlite:///{db_dir}/finance.db"
    )
    FinanceBase.metadata.create_all(finance_engine)
    with Session(work_engine) as work_session:
        def override_work():
            yield work_session

        def override_finance():
            session = finance_factory()
            try:
                yield session
            finally:
                session.close()

        app.dependency_overrides[get_session] = override_work
        app.dependency_overrides[get_finance_session] = override_finance
        monkeypatch.setattr(
            "faroflow.api.routes_unified.get_session_factory",
            lambda: finance_factory,
        )
        with TestClient(app) as client:
            yield client
        app.dependency_overrides.clear()


def _create_hierarchy(client) -> None:
    client.post(
        "/api/v1/workspaces",
        json={"id": "wrk_home", "name": "Local", "timezone": "America/Santiago"},
    )
    client.post(
        "/api/v1/clients",
        json={"id": "cli_home", "workspace_id": "wrk_home", "name": "Personal"},
    )
    client.post(
        "/api/v1/projects",
        json={"id": "prj_home", "client_id": "cli_home", "name": "Proyecto demo"},
    )


def _finance_household(client) -> tuple[str, str]:
    household = client.post(
        "/api/v1/finance/households",
        json={"name": "Hogar Prueba", "timezone": "America/Santiago"},
    ).json()
    client.post(
        f"/api/v1/finance/households/{household['id']}/members",
        json={"name": "yo", "role": "admin", "status": "active"},
    ).raise_for_status()
    account = client.post(
        "/api/v1/finance/accounts",
        json={
            "household_id": household["id"],
            "name": "Cuenta vista",
            "type": "checking",
            "currency": "CLP",
            "balance_reported": 0,
        },
    ).json()
    return household["id"], account["id"]


def _create_category(client, household_id: str) -> str:
    category = client.post(
        f"/api/v1/finance/households/{household_id}/categories",
        json={"name": "Alimentos", "kind": "expense"},
    ).json()
    return category["id"]


# ---------- Hábitos ----------


def test_habit_crud(api) -> None:
    response = api.post(
        "/api/v1/habits",
        json={
            "id": "hbt_agua",
            "name": "Beber agua",
            "goal_type": "quantity",
            "target_quantity": 8,
            "unit": "vasos",
            "frequency": "daily",
        },
    )
    assert response.status_code == 201
    created = response.json()
    assert created["unit"] == "vasos"

    listed = api.get("/api/v1/habits").json()
    assert [h["id"] for h in listed] == ["hbt_agua"]

    updated = api.patch("/api/v1/habits/hbt_agua", json={"status": "paused"})
    assert updated.status_code == 200
    assert updated.json()["status"] == "paused"

    deleted = api.delete("/api/v1/habits/hbt_agua")
    assert deleted.status_code == 204


def test_habit_binary_streak(api) -> None:
    from datetime import timedelta

    api.post("/api/v1/habits", json={"id": "hbt_ler", "name": "Leer"})
    today = date.today().isoformat()
    api.post("/api/v1/habits/hbt_ler/mark", json={"local_date": today})
    two_days_ago = (date.today() - timedelta(days=2)).isoformat()
    saw = api.post(
        "/api/v1/habits/hbt_ler/mark",
        json={"local_date": two_days_ago},
    )
    assert saw.status_code == 201

    third = (date.today() - timedelta(days=1)).isoformat()
    api.post("/api/v1/habits/hbt_ler/mark", json={"local_date": third})

    series = api.get("/api/v1/habits/hbt_ler/series").json()
    assert series["completed_today"] is True
    assert series["current_streak"] == 3

    # marcar dos veces el mismo día es idempotente
    api.post("/api/v1/habits/hbt_ler/mark", json={"local_date": today})
    assert len(series_completions(api, "hbt_ler")) == 3

    undone = api.post("/api/v1/habits/hbt_ler/unmark", json={"local_date": today})
    assert undone.status_code == 200
    assert undone.json()["completed_today"] is False


def series_completions(client, habit_id):
    return client.get(f"/api/v1/habits/{habit_id}/series").json()["completions"]


def test_habit_quantity_accumulates_and_external_dedupe(api) -> None:
    api.post(
        "/api/v1/habits",
        json={
            "id": "hbt_kms",
            "name": "Sesión de running",
            "goal_type": "quantity",
            "target_quantity": 10,
        },
    )
    api.post("/api/v1/habits/hbt_kms/mark", json={"quantity": 3})
    api.post("/api/v1/habits/hbt_kms/mark", json={"quantity": 4})
    series = api.get("/api/v1/habits/hbt_kms/series").json()
    assert series["today_quantity"] == 7
    assert series["completed_today"] is False

    api.post(
        "/api/v1/habits/hbt_kms/mark",
        json={"quantity": 6, "source": "telegram", "external_ref": "tg:42"},
    )
    api.post(
        "/api/v1/habits/hbt_kms/mark",
        json={"quantity": 6, "source": "telegram", "external_ref": "tg:42"},
    )
    series = api.get("/api/v1/habits/hbt_kms/series").json()
    assert series["today_quantity"] == 13
    assert series["completed_today"] is True


def test_habit_validation_rules(api) -> None:
    binary_target = api.post(
        "/api/v1/habits",
        json={"id": "hbt_bad", "name": "Mal", "goal_type": "binary", "target_quantity": 3},
    )
    assert binary_target.status_code == 422

    empty_days = api.post(
        "/api/v1/habits",
        json={"id": "hbt_bad2", "name": "Mal", "frequency": "specific_days", "specific_days": []},
    )
    assert empty_days.status_code == 422

    weekly_days = api.post(
        "/api/v1/habits",
        json={"id": "hbt_bad3", "name": "Mal", "frequency": "weekly", "specific_days": [1]},
    )
    assert weekly_days.status_code == 422

    archived = api.post(
        "/api/v1/habits",
        json={"id": "hbt_arc", "name": "Archivado", "status": "archived"},
    )
    assert archived.status_code == 201
    listed = api.get("/api/v1/habits?status=active").json()
    assert all(h["id"] != "hbt_arc" for h in listed)


def _week_of(client, habit_id):
    return client.get(f"/api/v1/habits/{habit_id}/series").json()["week"]


def test_habit_week_summary_spans_monday_to_sunday(api) -> None:
    api.post("/api/v1/habits", json={"id": "hbt_sem", "name": "Semanal"})
    week = _week_of(api, "hbt_sem")
    days = [d["date"] for d in week["days"]]

    assert len(days) == 7
    assert days[0] == week["start"] == days[0]
    assert days[-1] == week["end"]
    # la semana es siempre lunes a domingo, sin importar el día actual
    assert date.fromisoformat(days[0]).isoweekday() == 1
    assert date.fromisoformat(days[-1]).isoweekday() == 7
    assert week["days"][0]["is_today"] in (True, False)
    assert sum(1 for d in week["days"] if d["is_today"]) == 1


def test_habit_week_summary_ignores_future_days(api) -> None:
    api.post("/api/v1/habits", json={"id": "hbt_fut", "name": "Futuro"})
    week = _week_of(api, "hbt_fut")

    elapsed = [d for d in week["days"] if not d["is_future"]]
    future = [d for d in week["days"] if d["is_future"]]

    assert week["scheduled_days"] == len(elapsed)
    assert all(d["due"] is False for d in future)
    assert all(d["scheduled"] is True for d in future)
    # sin incumplimientos, la constancia de la semana es 0
    assert week["met_days"] == 0
    assert week["rate"] == 0.0
    assert week["goal_met"] is False


def test_habit_week_summary_counts_met_days(api) -> None:
    api.post("/api/v1/habits", json={"id": "hbt_dia", "name": "Diario"})
    week = _week_of(api, "hbt_dia")
    today = next(d["date"] for d in week["days"] if d["is_today"])

    api.post("/api/v1/habits/hbt_dia/mark", json={"local_date": today})
    met = _week_of(api, "hbt_dia")

    assert met["met_days"] == 1
    assert met["goal_met"] is True
    assert met["rate"] == round(1 / met["scheduled_days"], 2)
    today_day = next(d for d in met["days"] if d["is_today"])
    assert today_day["met"] is True
    assert today_day["quantity"] == 1


def test_habit_week_summary_skips_unscheduled_weekdays(api) -> None:
    api.post(
        "/api/v1/habits",
        json={"id": "hbt_lv", "name": "Laborables", "frequency": "weekdays"},
    )
    week = _week_of(api, "hbt_lv")

    for day in week["days"]:
        expected = date.fromisoformat(day["date"]).isoweekday() <= 5
        assert day["scheduled"] is expected
        if not expected:
            assert day["due"] is False
    # sábado y domingo nunca se contabilizan comoprogramados
    assert week["scheduled_days"] == sum(
        1
        for d in week["days"]
        if not d["is_future"] and date.fromisoformat(d["date"]).isoweekday() <= 5
    )


def test_habit_week_summary_resolves_weekly_goal(api) -> None:
    api.post(
        "/api/v1/habits",
        json={
            "id": "hbt_sem3",
            "name": "Tres por semana",
            "frequency": "weekly",
            "goal_type": "quantity",
            "target_quantity": 1,
            "weekly_target": 3,
        },
    )
    week = _week_of(api, "hbt_sem3")
    today = next(d["date"] for d in week["days"] if d["is_today"])
    assert week["goal_met"] is False

    for _ in range(3):
        api.post(
            "/api/v1/habits/hbt_sem3/mark",
            json={"local_date": today, "quantity": 1},
        )
    met = _week_of(api, "hbt_sem3")

    assert met["goal_met"] is True
    assert met["total_quantity"] == 3
    # un hábito semanal no marca días individuales como cumplidos
    assert all(d["met"] is False for d in met["days"])
    assert sum(1 for d in met["days"] if d["due"] and not d["is_future"]) == 0


# ---------- Bandeja ----------


def _receive(client, **overrides):
    payload = {
        "channel": "telegram",
        "author": "yo",
        "source_ref": "tg:1001",
        "original_text": "Comprar café de especialidad recargable",
    }
    payload.update(overrides)
    return client.post("/api/v1/bandeja", json=payload)


def test_bandeja_receive_deduplicates(api) -> None:
    first = _receive(api)
    assert first.status_code == 201
    second = _receive(api)
    assert second.status_code == 201
    assert second.json()["id"] == first.json()["id"]
    listed = api.get("/api/v1/bandeja?status=received").json()
    assert len(listed) == 1


def test_bandeja_routing_to_task(api) -> None:
    _create_hierarchy(api)
    item = _receive(api, source_ref="tg:1").json()
    response = api.post(
        f"/api/v1/bandeja/{item['id']}/apply",
        json={"decision": "task", "project_id": "prj_home", "priority": "high"},
    )
    assert response.status_code == 200
    applied = response.json()
    assert applied["status"] == "applied"
    assert applied["destination_module"] == "work"

    tasks = api.get("/api/v1/tasks").json()
    assert len(tasks) == 1
    assert tasks[0]["title"].startswith("Comprar café")
    assert tasks[0]["project_id"] == "prj_home"
    assert tasks[0]["status"] == "ready"


def test_bandeja_routing_to_expense(api) -> None:
    _household_id, _account_id = _finance_household(api)
    category_id = _create_category(api, _household_id)
    item = _receive(
        api,
        source_ref="tg:2",
        original_text="Almuerzo en la feria, 8500 pesos",
        kind="expense",
    ).json()
    response = api.post(
        f"/api/v1/bandeja/{item['id']}/apply",
        json={
            "decision": "expense",
            "amount": 8500,
            "account_id": _account_id,
            "category_id": category_id,
        },
    )
    assert response.status_code == 200, response.text
    assert response.json()["destination_module"] == "finance", response.text

    transactions = api.get("/api/v1/finance/transactions").json()
    assert len(transactions) == 1
    assert transactions[0]["type"] == "expense"
    assert transactions[0]["amount"] == 8500


def test_bandeja_routing_failure_marks_error(api) -> None:
    item = _receive(api, source_ref="tg:3", original_text="Gasto sin hogar").json()
    response = api.post(
        f"/api/v1/bandeja/{item['id']}/apply",
        json={"decision": "expense", "amount": 1000, "account_id": "acc_x"},
    )
    assert response.status_code == 422
    failed = api.get(f"/api/v1/bandeja/{item['id']}").json()
    assert failed["status"] == "error"
    assert failed["attempts"] == 1
    assert failed["error"]


def test_bandeja_refine_and_discard(api) -> None:
    item = _receive(api, source_ref="tg:4", original_text="Dormir 8 horas").json()
    refined = api.patch(
        f"/api/v1/bandeja/{item['id']}",
        json={"kind": "habit", "habit_id": "hbt_sueno"},
    )
    assert refined.status_code == 200
    assert refined.json()["kind"] == "habit"

    discarded = api.post(
        f"/api/v1/bandeja/{item['id']}/discard",
        json={"note": "Ya no aplica"},
    )
    assert discarded.status_code == 200
    assert discarded.json()["status"] == "discarded"

    pending = api.get("/api/v1/bandeja?status=received").json()
    assert [p["id"] for p in pending] == []


def test_bandeja_apply_habit(api) -> None:
    api.post("/api/v1/habits", json={"id": "hbt_sueno", "name": "Dormir"})
    item = _receive(api, source_ref="tg:5", original_text="Dormí temprano").json()
    response = api.post(
        f"/api/v1/bandeja/{item['id']}/apply",
        json={"decision": "habit", "habit_id": "hbt_sueno"},
    )
    assert response.status_code == 200
    assert response.json()["destination_module"] == "habits"
    series = api.get("/api/v1/habits/hbt_sueno/series").json()
    assert series["completed_today"] is True


# ---------- Bandeja: sugerencia de clasificación y decisión ----------


def test_bandeja_receive_persists_suggestion_kind_and_amount(api) -> None:
    response = api.post(
        "/api/v1/bandeja",
        json={
            "channel": "telegram",
            "author": "yo",
            "source_ref": "tg:sug1",
            "original_text": "Pagué 8500 pesos en el supermercado",
            "kind": "expense",
            "amount": 8500,
        },
    )
    assert response.status_code == 201
    stored = response.json()
    assert stored["kind"] == "expense"
    assert stored["amount"] == 8500
    assert stored["status"] == "received"


def test_bandeja_suggestion_never_auto_applies(api) -> None:
    _create_hierarchy(api)
    item = _receive(
        api,
        source_ref="tg:sug2",
        original_text="Pagué 8500 pesos en el supermercado",
        kind="expense",
    ).json()
    assert item["status"] == "received"
    assert item["destination_module"] is None
    pending = api.get("/api/v1/bandeja?status=received").json()
    assert [p["id"] for p in pending] == [item["id"]]


def test_bandeja_apply_records_resolved_at_and_decision_note(api) -> None:
    _create_hierarchy(api)
    item = _receive(
        api, source_ref="tg:sug3", original_text="Preparar informe para el lunes"
    ).json()
    response = api.post(
        f"/api/v1/bandeja/{item['id']}/apply",
        json={
            "decision": "task",
            "project_id": "prj_home",
            "priority": "high",
            "note": "Confirmado por prioridad del cliente",
        },
    )
    assert response.status_code == 200, response.text
    applied = response.json()
    assert applied["status"] == "applied"
    assert applied["destination_module"] == "work"
    assert applied["resolved_at"] is not None
    assert applied["decision_note"] == "Confirmado por prioridad del cliente"


def test_bandeja_apply_without_pending_proposal_is_explicit(api) -> None:
    _create_hierarchy(api)
    item = _receive(api, source_ref="tg:sug4").json()
    assert item["status"] == "received"
    # una captura solo se vincula si el humano la aplica
    tasks = api.get("/api/v1/tasks").json()
    assert tasks == []


def test_bandeja_discard_keeps_trail(api) -> None:
    item = _receive(api, source_ref="tg:sug5", original_text="Borrador").json()
    response = api.post(
        f"/api/v1/bandeja/{item['id']}/discard",
        json={"note": "No aplica"},
    )
    assert response.status_code == 200
    discarded = response.json()
    assert discarded["status"] == "discarded"
    assert discarded["decision_note"] == "No aplica"
    assert discarded["resolved_at"] is not None


# ---------- Bandeja: captura por chat (P4-02) ----------


def test_chat_inbound_lands_pending_and_dedupes(api) -> None:
    payload = {
        "channel": "telegram",
        "author": "yo",
        "source_ref": "tg:sim:1",
        "original_text": "Pagué 8500 pesos en el supermercado",
        "kind": "expense",
        "amount": 8500,
    }
    first = api.post("/api/v1/bandeja", json=payload)
    assert first.status_code == 201
    assert first.json()["status"] == "received"

    repeated = api.post("/api/v1/bandeja", json=payload)
    assert repeated.status_code == 201
    assert repeated.json()["id"] == first.json()["id"]

    by_channel = api.get("/api/v1/bandeja?channel=telegram").json()
    assert len(by_channel) == 1
    assert by_channel[0]["amount"] == 8500


def test_chat_inbound_never_auto_applies(api) -> None:
    _create_hierarchy(api)
    payload = {
        "channel": "telegram",
        "author": "yo",
        "source_ref": "tg:sim:2",
        "original_text": "Reunión con cliente mañana",
    }
    item = api.post("/api/v1/bandeja", json=payload).json()
    assert item["status"] == "received"
    assert item["destination_module"] is None

    tasks = api.get("/api/v1/tasks").json()
    assert tasks == []


def test_chat_inbound_classify_confirms_only_on_apply(api) -> None:
    _create_hierarchy(api)
    item = api.post(
        "/api/v1/bandeja",
        json={
            "channel": "telegram",
            "author": "yo",
            "source_ref": "tg:sim:3",
            "original_text": "Entregar informe del proyecto",
            "kind": "task",
        },
    ).json()
    assert item["kind"] == "task"

    confirmed = api.post(
        f"/api/v1/bandeja/{item['id']}/apply",
        json={"decision": "task", "project_id": "prj_home", "priority": "high"},
    )
    assert confirmed.status_code == 200
    assert confirmed.json()["status"] == "applied"
    assert confirmed.json()["destination_module"] == "work"

    tasks = api.get("/api/v1/tasks").json()
    assert len(tasks) == 1
    assert tasks[0]["title"] == "Entregar informe del proyecto"


# ---------- Mi día ----------


def test_home_aggregates_all_areas(api) -> None:
    _create_hierarchy(api)
    from datetime import UTC, datetime, timedelta

    api.post(
        "/api/v1/meetings",
        json={
            "id": "mtg_hoy",
            "title": "Standup",
            "starts_at": datetime.now(UTC).isoformat(),
        },
    )
    api.post(
        "/api/v1/tasks",
        json={
            "id": "tsk_vencida",
            "project_id": "prj_home",
            "title": "Tarea vencida",
            "due_at": (date.today() - timedelta(days=1)).isoformat(),
            "status": "ready",
        },
    )
    api.post("/api/v1/tasks/tsk_vencida/start")
    api.post("/api/v1/habits", json={"id": "hbt_diario", "name": "Meditar"})
    _receive(api, source_ref="tg:99", original_text="Revisar correo")
    household_id, _account_id = _finance_household(api)

    home = api.get("/api/v1/home")
    assert home.status_code == 200
    data = home.json()
    assert data["date"] == date.today().isoformat()
    assert data["work"]["count"] == 1
    assert data["meetings"]["count"] == 1
    assert data["bandeja"]["count"] == 1
    assert data["habits"][0]["id"] == "hbt_diario"
    assert data["habits"][0]["due_today"] is True
    assert data["habits"][0]["completed_today"] is False
    assert data["finance"]["available"] is True
    assert data["finance"]["household_id"] == household_id


def test_home_without_finance_is_resilient(api) -> None:
    _create_hierarchy(api)
    api.post("/api/v1/habits", json={"id": "hbt_fr", "name": "Fresco"})
    home = api.get("/api/v1/home")
    assert home.status_code == 200
    assert home.json()["finance"]["available"] is False
    assert home.json()["habits"][0]["id"] == "hbt_fr"


# ---------- Portabilidad ----------


def test_snapshot_includes_unified_home_entities(api) -> None:
    from faroflow.portability import export_snapshot, import_snapshot
    from faroflow.schemas import SnapshotDocument

    _create_hierarchy(api)
    api.post("/api/v1/habits", json={"id": "hbt_export", "name": "Exportar"})
    today = date.today().isoformat()
    api.post("/api/v1/habits/hbt_export/mark", json={"local_date": today})
    _receive(api, source_ref="tg:exp", original_text="Registro exportable")

    payload = api.get("/api/v1/snapshots/export").json()
    assert payload["schema_version"] == "1.2"
    assert len(payload["entities"]["habits"]) == 1
    assert len(payload["entities"]["habit_completions"]) == 1
    assert len(payload["entities"]["bandeja_items"]) == 1

    engine = build_engine("sqlite:///:memory:")
    WorkBase.metadata.create_all(engine)
    with Session(engine) as target:
        result = import_snapshot(target, SnapshotDocument.model_validate(payload))
        restored = export_snapshot(target)
    assert result["imported"]["habits"] == 1
    assert result["imported"]["habit_completions"] == 1
    assert result["imported"]["bandeja_items"] == 1
    assert restored["entities"]["bandeja_items"][0].source_ref == "tg:exp"
    assert {c.habit_id for c in restored["entities"]["habit_completions"]} == {"hbt_export"}