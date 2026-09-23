"""API de capturas de mensajería (Fase 4, CF4-03)."""

import pytest
from fastapi.testclient import TestClient

from cuentafaro.api import create_app
from cuentafaro.db import create_engine_and_session
from cuentafaro.deps import get_session
from cuentafaro.models import Base


@pytest.fixture()
def client(tmp_path):
    engine, session_factory = create_engine_and_session(f"sqlite:///{tmp_path / 'api_captures.db'}")
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


def _household(client, name="Hogar Capturas"):
    return client.post(
        "/api/v1/households",
        json={"name": name, "timezone": "America/Santiago", "status": "active"},
    ).json()


def _capture(client, household_id, kind="text", raw_text="Supermercado 45.890"):
    return client.post(
        f"/api/v1/households/{household_id}/captures",
        json={"kind": kind, "raw_text": raw_text},
    )


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


def _category(client, household_id, name="Alimentación"):
    categories = client.get(f"/api/v1/households/{household_id}/categories").json()
    return next(cat for cat in categories if cat["name"] == name)


def test_create_text_capture_pending(client) -> None:
    household = _household(client)
    response = _capture(client, household["id"], raw_text="Supermercado 45.890")
    assert response.status_code == 201
    capture = response.json()
    assert capture["id"].startswith("cap_")
    assert capture["household_id"] == household["id"]
    assert capture["channel"] == "simulated"
    assert capture["kind"] == "text"
    assert capture["raw_text"] == "Supermercado 45.890"
    assert capture["status"] == "pending"
    assert capture["confirmed_transaction_id"] is None
    assert capture["resolved_at"] is None
    assert capture["payload"] == {}


def test_create_audio_capture_with_payload(client) -> None:
    household = _household(client)
    response = client.post(
        f"/api/v1/households/{household['id']}/captures",
        json={"kind": "audio", "payload": {"media": "nota.ogg", "duration_s": 12}},
    )
    assert response.status_code == 201
    capture = response.json()
    assert capture["kind"] == "audio"
    assert capture["payload"]["media"] == "nota.ogg"


def test_create_capture_rejects_bad_kind(client) -> None:
    household = _household(client)
    response = client.post(f"/api/v1/households/{household['id']}/captures", json={"kind": "video"})
    assert response.status_code == 422


def test_list_captures_filters_by_status(client) -> None:
    household = _household(client)
    first = _capture(client, household["id"]).json()
    second = _capture(client, household["id"], raw_text="Otro mensaje").json()

    listed = client.get(f"/api/v1/households/{household['id']}/captures").json()
    assert {item["id"] for item in listed} == {first["id"], second["id"]}
    assert all(item["status"] == "pending" for item in listed)

    discarded = client.post(
        f"/api/v1/captures/{first['id']}/resolve", json={"resolution": "discard"}
    )
    assert discarded.status_code == 200
    assert discarded.json()["status"] == "discarded"

    pending = client.get(f"/api/v1/households/{household['id']}/captures?status=pending").json()
    assert {item["id"] for item in pending} == {second["id"]}


def test_get_capture_and_missing(client) -> None:
    household = _household(client)
    created = _capture(client, household["id"]).json()
    detail = client.get(f"/api/v1/captures/{created['id']}")
    assert detail.status_code == 200
    assert detail.json()["id"] == created["id"]
    assert client.get("/api/v1/captures/nope").status_code == 404


def test_resolve_discard_and_reject(client) -> None:
    household = _household(client)
    created = _capture(client, household["id"]).json()

    rejected = client.post(
        f"/api/v1/captures/{created['id']}/resolve", json={"resolution": "reject"}
    )
    assert rejected.status_code == 200
    body = rejected.json()
    assert body["status"] == "rejected"
    assert body["resolved_by"] == "manual"
    assert body["resolved_at"] is not None

    second = client.post(
        f"/api/v1/captures/{created['id']}/resolve", json={"resolution": "discard"}
    )
    assert second.status_code == 422
    assert "ya fue procesada" in second.json()["detail"]


def test_resolve_unsupported_resolution(client) -> None:
    household = _household(client)
    created = _capture(client, household["id"]).json()
    response = client.post(
        f"/api/v1/captures/{created['id']}/resolve", json={"resolution": "confirm"}
    )
    assert response.status_code == 422
    assert "reject" in response.json()["detail"][0]["msg"]


def test_captures_are_isolated_by_household(client) -> None:
    household_a = _household(client, name="Hogar A")
    household_b = client.post(
        "/api/v1/households",
        json={"name": "Hogar B", "timezone": "America/Santiago", "status": "archived"},
    ).json()
    _capture(client, household_a["id"])

    listed_b = client.get(f"/api/v1/households/{household_b['id']}/captures").json()
    assert listed_b == []


# ---------------- CF4-04 / CF4-05: procesar, corregir y confirmar ----------------


def test_process_text_capture_builds_proposal(client) -> None:
    household = _household(client)
    created = _capture(client, household["id"], raw_text="Supermercado 45.890").json()

    processed = client.post(f"/api/v1/captures/{created['id']}/process")
    assert processed.status_code == 200
    body = processed.json()
    assert body["status"] == "pending"
    proposal = body["payload"]["proposal"]
    assert proposal["amount"] == 45890
    assert proposal["description"] == "Supermercado"
    assert proposal["processed"] is True


def test_process_audio_capture_goes_needs_input(client) -> None:
    household = _household(client)
    created = client.post(
        f"/api/v1/households/{household['id']}/captures",
        json={"kind": "audio", "payload": {"media": "nota.ogg"}},
    ).json()

    processed = client.post(f"/api/v1/captures/{created['id']}/process")
    assert processed.status_code == 200
    body = processed.json()
    assert body["status"] == "needs_input"
    assert body["payload"]["proposal"]["processed"] is True
    assert body["raw_text"] is None


def test_process_with_rule_picks_suggested_category(client) -> None:
    household = _household(client)
    food = _category(client, household["id"])
    client.post(
        f"/api/v1/households/{household['id']}/import-category-rules",
        json={"column": "description", "pattern": "supermercado", "category_id": food["id"]},
    )
    created = _capture(client, household["id"], raw_text="Supermercado 45.890").json()

    processed = client.post(f"/api/v1/captures/{created['id']}/process").json()
    proposal = processed["payload"]["proposal"]
    assert proposal["suggestions"][0]["category_id"] == food["id"]
    assert proposal["category_id"] == food["id"]


def test_update_proposal_corrects_fields(client) -> None:
    household = _household(client)
    food = _category(client, household["id"])
    created = _capture(client, household["id"], raw_text="Supermercado 45.890").json()
    client.post(f"/api/v1/captures/{created['id']}/process")

    corrected = client.post(
        f"/api/v1/captures/{created['id']}/proposal",
        json={
            "amount": 60_000,
            "date": "2026-09-10",
            "description": "Supermercado corregido",
            "category_id": food["id"],
        },
    )
    assert corrected.status_code == 200
    proposal = corrected.json()["payload"]["proposal"]
    assert proposal["amount"] == 60000
    assert proposal["date"] == "2026-09-10"
    assert proposal["description"] == "Supermercado corregido"
    assert proposal["category_id"] == food["id"]


def test_confirm_capture_persists_transaction(client) -> None:
    household = _household(client)
    account = _account(client, household["id"])
    food = _category(client, household["id"])
    created = _capture(client, household["id"], raw_text="Supermercado 45.890").json()
    client.post(f"/api/v1/captures/{created['id']}/process")

    confirmed = client.post(
        f"/api/v1/captures/{created['id']}/confirm",
        json={"account_id": account["id"], "category_id": food["id"]},
    )
    assert confirmed.status_code == 200
    body = confirmed.json()
    assert body["status"] == "confirmed"
    assert body["confirmed_transaction_id"] is not None

    transactions = client.get(
        f"/api/v1/transactions?household_id={household['id']}&year=2026&month=9"
    ).json()
    created_txn = next(txn for txn in transactions if txn["id"] == body["confirmed_transaction_id"])
    assert created_txn["type"] == "expense"
    assert created_txn["amount"] == 45890
    assert created_txn["account_id"] == account["id"]
    assert created_txn["category_id"] == food["id"]
    assert created_txn["description"] == "Supermercado"

    account_after = client.get(f"/api/v1/accounts/{account['id']}").json()
    assert account_after["balance_calculated"] == 4_954_110


def test_confirm_with_overrides_wins_over_proposal(client) -> None:
    household = _household(client)
    account = _account(client, household["id"])
    created = _capture(client, household["id"], raw_text="Café 3.500").json()
    client.post(f"/api/v1/captures/{created['id']}/process")

    confirmed = client.post(
        f"/api/v1/captures/{created['id']}/confirm",
        json={
            "account_id": account["id"],
            "amount": 4_000,
            "date": "2026-08-01",
            "description": "Desayuno",
        },
    ).json()
    transactions = client.get(f"/api/v1/transactions?account_id={account['id']}").json()
    txn = next(item for item in transactions if item["id"] == confirmed["confirmed_transaction_id"])
    assert txn["amount"] == 4000
    assert txn["date"] == "2026-08-01"
    assert txn["description"] == "Desayuno"


def test_confirm_without_amount_rejected(client) -> None:
    household = _household(client)
    account = _account(client, household["id"])
    created = client.post(
        f"/api/v1/households/{household['id']}/captures",
        json={"kind": "audio", "payload": {"media": "nota.ogg"}},
    ).json()
    client.post(f"/api/v1/captures/{created['id']}/process")

    response = client.post(
        f"/api/v1/captures/{created['id']}/confirm", json={"account_id": account["id"]}
    )
    assert response.status_code == 422
    assert "no tiene monto" in response.json()["detail"]


def test_confirm_after_discard_rejected(client) -> None:
    household = _household(client)
    account = _account(client, household["id"])
    created = _capture(client, household["id"], raw_text="Supermercado 45.890").json()
    client.post(f"/api/v1/captures/{created['id']}/process")
    client.post(f"/api/v1/captures/{created['id']}/resolve", json={"resolution": "discard"})

    response = client.post(
        f"/api/v1/captures/{created['id']}/confirm", json={"account_id": account["id"]}
    )
    assert response.status_code == 422
    assert "ya fue procesada" in response.json()["detail"]
