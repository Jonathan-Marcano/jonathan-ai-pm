from datetime import UTC, date, datetime

import pytest

from faroflow.integrations import IntegrationStateError, IntegrationStateStore
from faroflow.models import ExternalIdentity, SyncRun
from faroflow.services import DomainStore


def build_targets(session) -> None:
    store = DomainStore(session)
    store.create("workspace", id="wrk_demo", name="Demo", timezone="America/Santiago")
    store.create("client", id="cli_demo", workspace_id="wrk_demo", name="Demo client")
    store.create("project", id="prj_demo", client_id="cli_demo", name="Demo project")
    store.create(
        "deliverable",
        id="del_demo",
        project_id="prj_demo",
        title="MOP draft",
        due_at=date(2026, 9, 18),
    )
    store.create(
        "meeting",
        id="mtg_demo",
        project_id="prj_demo",
        title="Client review",
        starts_at=datetime(2026, 9, 15, 16, 0, tzinfo=UTC),
    )


def test_external_identity_upsert_is_stable_and_updates_metadata(session) -> None:
    build_targets(session)
    state = IntegrationStateStore(session)
    first = state.upsert_identity(
        entity_kind="meeting",
        entity_id="mtg_demo",
        source_system="Microsoft-365",
        external_scope="work-calendar",
        external_id="event-123",
        external_version="v1",
        web_url="https://example.test/events/event-123",
        synced_at=datetime(2026, 9, 14, 12, 0, tzinfo=UTC),
    )
    updated = state.upsert_identity(
        entity_kind="meeting",
        entity_id="mtg_demo",
        source_system="microsoft-365",
        external_scope="work-calendar",
        external_id="event-123",
        external_version="v2",
        synced_at=datetime(2026, 9, 14, 13, 0, tzinfo=UTC),
    )

    assert updated.id == first.id
    assert updated.external_version == "v2"
    assert updated.web_url is None
    assert session.query(ExternalIdentity).count() == 1


def test_external_identity_cannot_move_to_another_entity(session) -> None:
    build_targets(session)
    state = IntegrationStateStore(session)
    state.upsert_identity(
        entity_kind="meeting",
        entity_id="mtg_demo",
        source_system="microsoft-365",
        external_scope="work-calendar",
        external_id="event-123",
    )
    with pytest.raises(IntegrationStateError, match="already linked"):
        state.upsert_identity(
            entity_kind="deliverable",
            entity_id="del_demo",
            source_system="microsoft-365",
            external_scope="work-calendar",
            external_id="event-123",
        )


def test_sync_run_records_counts_and_redacted_errors(session) -> None:
    state = IntegrationStateStore(session)
    run = state.start_run(
        source_system="Microsoft-365",
        resource_kind="calendar",
        external_scope="work-calendar",
        window_starts_at=datetime(2026, 9, 14, 0, 0, tzinfo=UTC),
        window_ends_at=datetime(2026, 9, 21, 0, 0, tzinfo=UTC),
        started_at=datetime(2026, 9, 14, 12, 0, tzinfo=UTC),
    )
    error = state.record_error(
        run.id,
        code="Provider_Error",
        message="request failed: Authorization: Bearer secret-token; password=hunter2",
        occurred_at=datetime(2026, 9, 14, 12, 1, tzinfo=UTC),
    )
    finished = state.finish_run(
        run.id,
        seen_count=3,
        created_count=1,
        unchanged_count=1,
        skipped_count=1,
        completed_at=datetime(2026, 9, 14, 12, 2, tzinfo=UTC),
    )

    assert finished.status == "partial"
    assert finished.error_count == 1
    assert finished.seen_count == 3
    assert "secret-token" not in error.message
    assert "hunter2" not in error.message
    assert error.message.count("[REDACTED]") >= 2
    assert state.list_errors(run.id) == [error]


def test_successful_sync_run_is_auditable_without_credentials(session) -> None:
    state = IntegrationStateStore(session)
    run = state.start_run(source_system="google-drive", resource_kind="document")
    finished = state.finish_run(run.id, seen_count=2, created_count=2)

    stored = session.get(SyncRun, run.id)
    assert finished.status == "succeeded"
    assert stored is not None
    assert stored.source_system == "google-drive"
    assert stored.created_count == 2
    assert not hasattr(stored, "access_token")
    assert not hasattr(stored, "refresh_token")


def test_sync_run_rejects_invalid_windows_counts_and_second_finish(session) -> None:
    state = IntegrationStateStore(session)
    with pytest.raises(IntegrationStateError, match="both timestamps"):
        state.start_run(
            source_system="microsoft-365",
            resource_kind="calendar",
            window_starts_at=datetime(2026, 9, 14, 0, 0, tzinfo=UTC),
        )
    run = state.start_run(source_system="microsoft-365", resource_kind="calendar")
    with pytest.raises(IntegrationStateError, match="add up"):
        state.finish_run(run.id, seen_count=2, created_count=1)
    state.finish_run(run.id, seen_count=1, unchanged_count=1)
    with pytest.raises(IntegrationStateError, match="already completed"):
        state.finish_run(run.id, seen_count=1, unchanged_count=1)
