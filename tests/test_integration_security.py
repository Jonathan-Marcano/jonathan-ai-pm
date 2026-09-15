from datetime import UTC, datetime, timedelta

import pytest
from pydantic import ValidationError
from sqlalchemy import select

from jonathan_ai_pm.config import Settings
from jonathan_ai_pm.integrations import (
    CalendarReconciler,
    CalendarWindow,
    IntegrationCapabilities,
    IntegrationMaintenanceService,
    IntegrationSecurityError,
    IntegrationStateStore,
    Microsoft365CalendarAdapter,
    Microsoft365CalendarConfig,
    Microsoft365CalendarError,
    require_read_only_capabilities,
    validate_microsoft_graph_permissions,
)
from jonathan_ai_pm.models import (
    CalendarImportReview,
    CalendarProjectMapping,
    ExternalIdentity,
    Meeting,
    SyncRun,
    SyncRunError,
)
from jonathan_ai_pm.services import DomainStore

NOW = datetime(2026, 9, 15, 12, tzinfo=UTC)
SOURCE = "microsoft-365"
SCOPE = "work-a:default"


def build_project(session) -> Meeting:
    store = DomainStore(session)
    store.create("workspace", id="wrk_demo", name="Demo", timezone="America/Santiago")
    store.create("client", id="cli_demo", workspace_id="wrk_demo", name="Demo client")
    store.create("project", id="prj_demo", client_id="cli_demo", name="Demo project")
    return store.create(
        "meeting",
        id="mtg_demo",
        project_id="prj_demo",
        title="Client review",
        starts_at=NOW + timedelta(days=1),
    )


def add_calendar_metadata(session, meeting: Meeting) -> ExternalIdentity:
    identity = IntegrationStateStore(session).upsert_identity(
        entity_kind="meeting",
        entity_id=meeting.id,
        source_system=SOURCE,
        external_scope=SCOPE,
        external_id="event-123",
        web_url="https://example.test/events/event-123",
        synced_at=NOW,
    )
    session.add_all(
        [
            CalendarProjectMapping(
                id="calmap_demo",
                source_system=SOURCE,
                external_scope=SCOPE,
                external_id="event-123",
                project_id="prj_demo",
                confirmed_by="jonathan",
                confirmed_at=NOW,
            ),
            CalendarImportReview(
                id="calrev_demo",
                source_system=SOURCE,
                external_scope=SCOPE,
                external_id="event-123",
                title="Client review",
                starts_at=meeting.starts_at,
                ends_at=meeting.starts_at + timedelta(hours=1),
                event_status="confirmed",
                web_url="https://example.test/events/event-123",
                external_modified_at=NOW,
                status="resolved",
                first_seen_at=NOW,
                last_seen_at=NOW,
                resolution_project_id="prj_demo",
                resolved_by="jonathan",
                resolved_at=NOW,
            ),
        ]
    )
    session.commit()
    return identity


def test_permission_policy_allows_only_declared_read_scopes() -> None:
    assert validate_microsoft_graph_permissions("Calendars.ReadBasic openid offline_access") == (
        "calendars.readbasic",
        "openid",
        "offline_access",
    )

    with pytest.raises(IntegrationSecurityError, match="not approved"):
        validate_microsoft_graph_permissions("Calendars.ReadWrite")
    with pytest.raises(IntegrationSecurityError, match="requires Calendars.ReadBasic"):
        validate_microsoft_graph_permissions("openid")


def test_settings_reject_write_scope_and_invalid_retention() -> None:
    with pytest.raises(ValidationError, match="not approved"):
        Settings(
            _env_file=None,
            microsoft_calendar_enabled=True,
            microsoft_graph_scopes="Calendars.ReadWrite",
        )
    with pytest.raises(ValidationError, match="greater than or equal to 1"):
        Settings(_env_file=None, integration_sync_history_retention_days=0)


def test_microsoft_adapter_config_rejects_write_permission() -> None:
    with pytest.raises(Microsoft365CalendarError, match="not approved"):
        Microsoft365CalendarConfig(requested_permissions=("Calendars.ReadWrite",))


def test_microsoft_adapter_rechecks_capabilities_before_request() -> None:
    adapter = Microsoft365CalendarAdapter(lambda: "unused-fictional-token")
    adapter.capabilities = IntegrationCapabilities(
        read=True,
        create=False,
        update=True,
        delete=False,
    )

    with pytest.raises(Microsoft365CalendarError, match="write capabilities"):
        adapter.list_events(
            CalendarWindow(starts_at=NOW, ends_at=NOW + timedelta(days=1))
        )


def test_reconciliation_rejects_write_capability_before_run(session) -> None:
    unsafe = IntegrationCapabilities(read=True, create=False, update=True, delete=False)
    with pytest.raises(IntegrationSecurityError, match="write capabilities"):
        require_read_only_capabilities(unsafe)
    with pytest.raises(IntegrationSecurityError, match="write capabilities"):
        CalendarReconciler(session).reconcile(
            [],
            window=CalendarWindow(
                starts_at=NOW,
                ends_at=NOW + timedelta(days=1),
            ),
            source_system=SOURCE,
            external_scope=SCOPE,
            capabilities=unsafe,
        )
    assert session.query(SyncRun).count() == 0


def test_retention_deletes_only_expired_completed_state(session) -> None:
    meeting = build_project(session)
    add_calendar_metadata(session, meeting)
    state = IntegrationStateStore(session)
    old_run = state.start_run(
        source_system=SOURCE,
        resource_kind="calendar",
        external_scope=SCOPE,
        started_at=NOW - timedelta(days=100),
    )
    state.record_error(
        old_run.id,
        code="provider_error",
        message="fictional failure",
        occurred_at=NOW - timedelta(days=100),
    )
    state.finish_run(
        old_run.id,
        seen_count=1,
        skipped_count=1,
        completed_at=NOW - timedelta(days=100) + timedelta(minutes=1),
    )
    recent_run = state.start_run(
        source_system=SOURCE,
        resource_kind="calendar",
        external_scope=SCOPE,
        started_at=NOW - timedelta(days=2),
    )
    state.finish_run(
        recent_run.id,
        seen_count=0,
        completed_at=NOW - timedelta(days=2) + timedelta(minutes=1),
    )
    running = state.start_run(
        source_system=SOURCE,
        resource_kind="calendar",
        external_scope=SCOPE,
        started_at=NOW - timedelta(days=100),
    )
    old_run_id = old_run.id
    recent_run_id = recent_run.id
    running_id = running.id
    resolved = session.get(CalendarImportReview, "calrev_demo")
    resolved.resolved_at = NOW - timedelta(days=40)
    session.add(
        CalendarImportReview(
            id="calrev_pending",
            source_system=SOURCE,
            external_scope=SCOPE,
            external_id="event-pending",
            title="Pending review",
            starts_at=NOW - timedelta(days=60),
            ends_at=NOW - timedelta(days=60) + timedelta(hours=1),
            event_status="confirmed",
            web_url=None,
            external_modified_at=None,
            status="pending",
            first_seen_at=NOW - timedelta(days=60),
            last_seen_at=NOW - timedelta(days=60),
            resolution_project_id=None,
            resolved_by=None,
            resolved_at=None,
        )
    )
    session.commit()

    result = IntegrationMaintenanceService(session).enforce_retention(
        sync_history_days=90,
        resolved_review_days=30,
        as_of=NOW,
    )

    assert result.sync_runs_deleted == 1
    assert result.resolved_reviews_deleted == 1
    assert session.get(SyncRun, old_run_id) is None
    assert session.get(SyncRun, recent_run_id) is not None
    assert session.get(SyncRun, running_id) is not None
    assert session.get(CalendarImportReview, "calrev_pending") is not None
    assert session.get(CalendarProjectMapping, "calmap_demo") is not None
    assert session.query(SyncRunError).count() == 0


def test_disconnect_removes_provider_links_but_keeps_operational_meeting(session) -> None:
    meeting = build_project(session)
    identity = add_calendar_metadata(session, meeting)
    state = IntegrationStateStore(session)
    run = state.start_run(
        source_system=SOURCE,
        resource_kind="calendar",
        external_scope=SCOPE,
        started_at=NOW,
    )
    error = state.record_error(
        run.id,
        code="provider_error",
        message="fictional failure",
        external_identity_id=identity.id,
        occurred_at=NOW,
    )
    state.finish_run(
        run.id,
        seen_count=1,
        skipped_count=1,
        completed_at=NOW + timedelta(minutes=1),
    )

    result = IntegrationMaintenanceService(session).disconnect(
        "Microsoft-365", external_scope=SCOPE
    )
    session.expire_all()

    assert result.identities_deleted == 1
    assert result.reviews_deleted == 1
    assert result.mappings_deleted == 1
    assert result.sync_runs_anonymized == 1
    assert session.get(Meeting, meeting.id) is not None
    assert session.query(ExternalIdentity).count() == 0
    assert session.query(CalendarImportReview).count() == 0
    assert session.query(CalendarProjectMapping).count() == 0
    assert session.get(SyncRun, run.id).external_scope is None
    assert session.get(SyncRunError, error.id).external_identity_id is None


def test_disconnect_can_target_one_scope_without_touching_another(session) -> None:
    meeting = build_project(session)
    add_calendar_metadata(session, meeting)
    session.add(
        ExternalIdentity(
            id="ext_other",
            entity_kind="meeting",
            entity_id=meeting.id,
            source_system=SOURCE,
            external_scope="work-b:default",
            external_id="event-other",
            external_version=None,
            web_url=None,
            external_modified_at=None,
            last_synced_at=NOW,
            missing_since=None,
        )
    )
    session.commit()

    IntegrationMaintenanceService(session).disconnect(SOURCE, external_scope=SCOPE)

    remaining = session.scalars(select(ExternalIdentity)).all()
    assert [identity.external_scope for identity in remaining] == ["work-b:default"]
