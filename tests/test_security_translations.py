import stat

import pytest

from faroflow.db import build_engine
from faroflow.security import REDACTED, redact_text, redact_value, write_private_text


def create_task(api_client) -> None:
    api_client.post(
        "/api/v1/workspaces",
        json={"id": "wrk_demo", "name": "Demo", "timezone": "America/Santiago"},
    )
    api_client.post(
        "/api/v1/clients",
        json={"id": "cli_demo", "workspace_id": "wrk_demo", "name": "Client"},
    )
    api_client.post(
        "/api/v1/projects",
        json={"id": "prj_demo", "client_id": "cli_demo", "name": "Project"},
    )
    api_client.post(
        "/api/v1/tasks",
        json={"id": "tsk_demo", "project_id": "prj_demo", "title": "Preparar MOP"},
    )


def test_local_sqlite_file_uses_private_permissions(tmp_path) -> None:
    database_path = tmp_path / "private" / "app.db"
    engine = build_engine(f"sqlite:///{database_path}")

    assert stat.S_IMODE(database_path.stat().st_mode) == 0o600
    assert stat.S_IMODE(database_path.parent.stat().st_mode) == 0o700
    engine.dispose()


def test_private_backup_refuses_implicit_overwrite(tmp_path) -> None:
    backup_path = tmp_path / "backups" / "demo.snapshot.json"
    write_private_text(backup_path, '{"schema_version":"1.1"}')

    assert stat.S_IMODE(backup_path.stat().st_mode) == 0o600
    with pytest.raises(FileExistsError):
        write_private_text(backup_path, "replacement")
    assert backup_path.read_text(encoding="utf-8") == '{"schema_version":"1.1"}'

    write_private_text(backup_path, "replacement", overwrite=True)
    assert backup_path.read_text(encoding="utf-8") == "replacement"


def test_sensitive_values_are_redacted() -> None:
    message = "Authorization: Bearer abc123; password=secret, api_key=key123"
    redacted = redact_text(message)
    assert "abc123" not in redacted
    assert "secret" not in redacted
    assert "key123" not in redacted
    assert REDACTED in redacted

    payload = redact_value({"token": "abc", "nested": {"password": "secret"}, "safe": "visible"})
    assert payload == {
        "token": REDACTED,
        "nested": {"password": REDACTED},
        "safe": "visible",
    }


def test_request_logging_redacts_sensitive_query_values(api_client, caplog) -> None:
    import logging

    caplog.set_level(logging.INFO, logger="faroflow.api")
    api_client.get("/api/v1/tasks?status=ready&api_key=secret123")

    logged = [record.message for record in caplog.records]
    assert any("api_key=[REDACTED]" in message for message in logged)
    assert all("secret123" not in message for message in logged)


def test_manual_translation_preserves_original_and_is_audited(api_client) -> None:
    create_task(api_client)
    created = api_client.post(
        "/api/v1/translations",
        headers={"X-Actor": "jonathan"},
        json={
            "id": "trn_task_pt",
            "entity_kind": "task",
            "entity_id": "tsk_demo",
            "field_name": "title",
            "language": "pt-BR",
            "translated_text": "Preparar MOP em português",
        },
    )
    assert created.status_code == 201
    assert api_client.get("/api/v1/tasks/tsk_demo").json()["title"] == "Preparar MOP"

    updated = api_client.patch(
        "/api/v1/translations/trn_task_pt",
        headers={"X-Actor": "jonathan"},
        json={"translated_text": "Preparar o MOP"},
    )
    assert updated.status_code == 200
    assert updated.json()["translated_text"] == "Preparar o MOP"

    filtered = api_client.get(
        "/api/v1/translations?entity_kind=task&entity_id=tsk_demo&language=pt-BR"
    )
    assert [item["id"] for item in filtered.json()] == ["trn_task_pt"]
    audit = api_client.get(
        "/api/v1/audit-events?entity_kind=translation&entity_id=trn_task_pt"
    ).json()
    assert [event["action"] for event in audit] == ["create", "update"]


def test_translation_validates_target_field_and_uniqueness(api_client) -> None:
    create_task(api_client)
    payload = {
        "id": "trn_task_en",
        "entity_kind": "task",
        "entity_id": "tsk_demo",
        "field_name": "title",
        "language": "en",
        "translated_text": "Prepare MOP",
    }
    assert api_client.post("/api/v1/translations", json=payload).status_code == 201

    duplicate = {**payload, "id": "trn_task_en_duplicate"}
    assert api_client.post("/api/v1/translations", json=duplicate).status_code == 409

    wrong_field = {
        **payload,
        "id": "trn_wrong_field",
        "field_name": "name",
        "language": "es",
    }
    assert api_client.post("/api/v1/translations", json=wrong_field).status_code == 422


def test_source_cannot_be_deleted_before_translation(api_client) -> None:
    create_task(api_client)
    api_client.post(
        "/api/v1/translations",
        json={
            "id": "trn_task_en",
            "entity_kind": "task",
            "entity_id": "tsk_demo",
            "field_name": "title",
            "language": "en",
            "translated_text": "Prepare MOP",
        },
    )

    blocked = api_client.delete("/api/v1/tasks/tsk_demo")
    # 409 y no 422: el registro esta bien, lo que falta es desenlazar la referencia.
    assert blocked.status_code == 409
    assert api_client.delete("/api/v1/translations/trn_task_en").status_code == 204
    assert api_client.delete("/api/v1/tasks/tsk_demo").status_code == 204


def test_snapshot_1_1_includes_translations_and_accepts_1_0(api_client) -> None:
    create_task(api_client)
    api_client.post(
        "/api/v1/translations",
        json={
            "id": "trn_task_en",
            "entity_kind": "task",
            "entity_id": "tsk_demo",
            "field_name": "title",
            "language": "en",
            "translated_text": "Prepare MOP",
        },
    )
    current = api_client.get("/api/v1/snapshots/export").json()
    assert current["schema_version"] == "1.2"
    assert current["entities"]["translations"][0]["id"] == "trn_task_en"

    legacy = {**current, "schema_version": "1.0"}
    legacy["entities"] = {**current["entities"]}
    legacy["entities"].pop("translations")
    nonempty = api_client.post("/api/v1/snapshots/import", json=legacy)
    assert nonempty.status_code == 422
    assert nonempty.json()["detail"] == "Snapshot import requires an empty datastore"
