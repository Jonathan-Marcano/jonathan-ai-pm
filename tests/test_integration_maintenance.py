from datetime import UTC, datetime, timedelta

import pytest

from faroflow.config import Settings
from faroflow.integrations.maintenance import (
    IntegrationMaintenanceError,
    IntegrationMaintenanceService,
)
from faroflow.integrations.persistence import IntegrationStateStore
from faroflow.models import ExternalIdentity, MeetingProjectMapping, SyncRun
from faroflow.services import DomainStore

NOW = datetime(2026, 9, 23, 12, 0, tzinfo=UTC)


def build_identity(session, *, source_system="google-drive", scope="", external_id="file-1"):
    return IntegrationStateStore(session).upsert_identity(
        entity_kind="deliverable",
        entity_id="dlv_demo",
        source_system=source_system,
        external_scope=scope,
        external_id=external_id,
        external_name="Plan.pdf",
        web_url=f"https://drive.example.test/{external_id}",
        mime_type="application/pdf",
    )


def build_workspace(session) -> None:
    store = DomainStore(session)
    store.create("workspace", id="wrk_demo", name="Demo", timezone="America/Santiago")
    store.create("client", id="cli_demo", workspace_id="wrk_demo", name="Demo client")
    store.create("project", id="prj_demo", client_id="cli_demo", name="Demo project")
    store.create("deliverable", id="dlv_demo", project_id="prj_demo", title="Plan",
                 due_at=datetime(2026, 9, 30, tzinfo=UTC).date())


def seed_run(session, *, days_ago: int, with_error: bool) -> SyncRun:
    state = IntegrationStateStore(session)
    run = state.start_run(
        source_system="mocked-365",
        resource_kind="calendar",
        external_scope="cal",
        started_at=NOW - timedelta(days=days_ago),
    )
    if with_error:
        state.record_error(run.id, code="http_429", message="rate limited")
    state.finish_run(
        run.id,
        seen_count=1,
        created_count=1,
        status="succeeded" if not with_error else "partial",
    )
    return run


def test_retention_deletes_expired_runs_and_errors(session) -> None:
    old_id = seed_run(session, days_ago=120, with_error=True).id
    recent_id = seed_run(session, days_ago=1, with_error=False).id

    result = IntegrationMaintenanceService(session).enforce_retention(sync_history_days=90)

    assert result.sync_runs_deleted == 1
    assert result.sync_run_errors_deleted == 1
    assert session.query(SyncRun.id).filter_by(id=old_id).count() == 0
    assert session.query(SyncRun.id).filter_by(id=recent_id).count() == 1


def test_retention_validates_arguments(session) -> None:
    service = IntegrationMaintenanceService(session)
    with pytest.raises(IntegrationMaintenanceError):
        service.enforce_retention(sync_history_days=0)
    with pytest.raises(IntegrationMaintenanceError):
        service.enforce_retention(sync_history_days=True)
    with pytest.raises(IntegrationMaintenanceError):
        service.enforce_retention(sync_history_days=10, as_of=NOW.replace(tzinfo=None))


def test_disconnect_removes_links_and_anonymizes_runs(session) -> None:
    build_workspace(session)
    build_identity(session)
    run = IntegrationStateStore(session).start_run(
        source_system="google-drive", resource_kind="document", external_scope=""
    )
    run_id = run.id
    IntegrationStateStore(session).finish_run(run.id, seen_count=0)

    mapping = IntegrationStateStore(session).set_project_mapping(
        source_system="google-drive",
        external_scope="",
        external_id="mapped-1",
        project_id="prj_demo",
    )
    mapping_id = mapping.id

    result = IntegrationMaintenanceService(session).disconnect("google-drive")

    assert result.identities_deleted == 1
    assert result.mappings_deleted == 1
    assert result.sync_runs_anonymized == 1
    assert session.query(ExternalIdentity).count() == 0
    assert session.query(MeetingProjectMapping.id).filter_by(id=mapping_id).count() == 0
    persisted = session.query(SyncRun).filter_by(id=run_id).one()
    assert persisted.source_system == "disconnected"
    assert persisted.external_scope is None


def test_disconnect_scoped_filters(session) -> None:
    build_workspace(session)
    build_identity(session, source_system="google-drive", scope="base")
    build_identity(session, source_system="google-drive", scope="private")

    result = IntegrationMaintenanceService(session).disconnect(
        "google-drive", external_scope="base"
    )

    assert result.identities_deleted == 1


def test_protected_operations_gate_when_disabled(api_client) -> None:
    response = api_client.delete(
        "/api/v1/integrations/meeting-project-mappings/nonexistent",
        headers={"X-Integration-Key": "any-key"},
    )
    assert response.status_code == 404


def test_protected_operations_require_key(api_client, monkeypatch) -> None:
    settings = Settings(
        integration_operations_enabled=True,
        integration_operation_key="x" * 32,
    )
    monkeypatch.setattr("faroflow.api.deps.get_settings", lambda: settings)

    missing = api_client.delete("/api/v1/integrations/meeting-project-mappings/nonexistent")
    assert missing.status_code == 401

    wrong = api_client.delete(
        "/api/v1/integrations/meeting-project-mappings/nonexistent",
        headers={"X-Integration-Key": "wrong-key"},
    )
    assert wrong.status_code == 401

    valid = api_client.delete(
        "/api/v1/integrations/meeting-project-mappings/nonexistent",
        headers={"X-Integration-Key": "x" * 32},
    )
    assert valid.status_code == 404