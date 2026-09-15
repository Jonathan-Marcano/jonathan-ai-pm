from datetime import UTC, datetime, timedelta

import pytest

from jonathan_ai_pm.api import (
    app,
    get_calendar_adapter_registry,
    get_integration_settings,
)
from jonathan_ai_pm.config import Settings
from jonathan_ai_pm.integrations import (
    READ_ONLY_CAPABILITIES,
    CalendarAdapterRegistry,
    CalendarWindow,
    ExternalCalendarEvent,
)
from jonathan_ai_pm.models import Meeting
from jonathan_ai_pm.services import DomainStore

SOURCE = "microsoft-365"
SCOPE = "work-a:default"
OPERATION_KEY = "fictional-operation-key-32-characters"
STARTS_AT = datetime(2026, 9, 15, 0, tzinfo=UTC)
ENDS_AT = STARTS_AT + timedelta(days=7)


class FakeCalendarAdapter:
    source_system = SOURCE
    capabilities = READ_ONLY_CAPABILITIES

    def __init__(self, events: list[ExternalCalendarEvent] | None = None) -> None:
        self.events = events or []
        self.windows: list[CalendarWindow] = []

    def list_events(self, window: CalendarWindow) -> list[ExternalCalendarEvent]:
        self.windows.append(window)
        return self.events


class FailingCalendarAdapter(FakeCalendarAdapter):
    def list_events(self, window: CalendarWindow) -> list[ExternalCalendarEvent]:
        self.windows.append(window)
        raise RuntimeError("Authorization: Bearer fictional-secret-token")


def event(external_id: str = "event-123") -> ExternalCalendarEvent:
    return ExternalCalendarEvent(
        source_system=SOURCE,
        calendar_id=SCOPE,
        external_id=external_id,
        title="Client review",
        starts_at=STARTS_AT + timedelta(days=1, hours=16),
        ends_at=STARTS_AT + timedelta(days=1, hours=17),
        web_url=f"https://example.test/events/{external_id}",
        last_modified_at=STARTS_AT,
    )


def build_project(session) -> None:
    store = DomainStore(session)
    store.create("workspace", id="wrk_demo", name="Demo", timezone="America/Santiago")
    store.create("client", id="cli_demo", workspace_id="wrk_demo", name="Demo client")
    store.create("project", id="prj_demo", client_id="cli_demo", name="Demo project")


def sync_payload() -> dict[str, str]:
    return {
        "source_system": SOURCE,
        "external_scope": SCOPE,
        "starts_at": STARTS_AT.isoformat(),
        "ends_at": ENDS_AT.isoformat(),
    }


@pytest.fixture
def registry() -> CalendarAdapterRegistry:
    return CalendarAdapterRegistry()


@pytest.fixture
def operations_client(api_client, registry):
    settings = Settings(
        _env_file=None,
        microsoft_calendar_enabled=True,
        microsoft_calendar_ids=SCOPE,
        integration_operations_enabled=True,
        integration_operation_key=OPERATION_KEY,
        integration_max_sync_window_days=31,
    )
    app.dependency_overrides[get_integration_settings] = lambda: settings
    app.dependency_overrides[get_calendar_adapter_registry] = lambda: registry
    api_client.headers.update({"X-Integration-Key": OPERATION_KEY, "X-Actor": "jonathan"})
    yield api_client


def test_operations_are_key_protected_and_can_be_disabled(api_client, registry) -> None:
    enabled = Settings(
        _env_file=None,
        microsoft_calendar_enabled=True,
        integration_operations_enabled=True,
        integration_operation_key=OPERATION_KEY,
    )
    app.dependency_overrides[get_integration_settings] = lambda: enabled
    app.dependency_overrides[get_calendar_adapter_registry] = lambda: registry

    assert api_client.get("/api/v1/integrations/status").status_code == 401
    assert (
        api_client.get(
            "/api/v1/integrations/status",
            headers={"X-Integration-Key": "wrong-key"},
        ).status_code
        == 401
    )

    disabled = Settings(_env_file=None, integration_operations_enabled=False)
    app.dependency_overrides[get_integration_settings] = lambda: disabled
    response = api_client.get(
        "/api/v1/integrations/status",
        headers={"X-Integration-Key": OPERATION_KEY},
    )
    assert response.status_code == 503


def test_status_and_manual_sync_queue_review_without_guessing_project(
    operations_client, registry, session
) -> None:
    adapter = FakeCalendarAdapter([event()])
    registry.register(source_system=SOURCE, external_scope=SCOPE, adapter=adapter)

    status = operations_client.get("/api/v1/integrations/status")
    assert status.status_code == 200
    connection = status.json()["connections"][0]
    assert connection == {
        "source_system": SOURCE,
        "external_scope": SCOPE,
        "enabled": True,
        "adapter_available": True,
        "read_only": True,
        "ready": True,
        "permissions": ["calendars.readbasic"],
        "last_run": None,
    }
    assert OPERATION_KEY not in status.text

    response = operations_client.post("/api/v1/integrations/calendar/sync", json=sync_payload())
    assert response.status_code == 200
    result = response.json()
    assert result["status"] == "succeeded"
    assert result["skipped_count"] == 1
    assert len(result["queued_review_ids"]) == 1
    assert session.query(Meeting).count() == 0

    runs = operations_client.get("/api/v1/integrations/sync-runs")
    assert runs.status_code == 200
    assert runs.json()[0]["id"] == result["run_id"]
    assert runs.json()[0]["retryable"] is False
    detail = operations_client.get(f"/api/v1/integrations/sync-runs/{result['run_id']}")
    assert detail.status_code == 200
    assert detail.json()["external_scope"] == SCOPE
    assert (
        operations_client.get(f"/api/v1/integrations/sync-runs/{result['run_id']}/errors").json()
        == []
    )


def test_review_confirmation_and_dismissal_are_explicit(
    operations_client, registry, session
) -> None:
    build_project(session)
    adapter = FakeCalendarAdapter([event("event-confirm"), event("event-dismiss")])
    registry.register(source_system=SOURCE, external_scope=SCOPE, adapter=adapter)
    operations_client.post("/api/v1/integrations/calendar/sync", json=sync_payload())

    pending = operations_client.get("/api/v1/integrations/calendar/reviews")
    assert pending.status_code == 200
    assert len(pending.json()) == 2
    confirm_id, dismiss_id = [item["id"] for item in pending.json()]

    confirmed = operations_client.post(
        f"/api/v1/integrations/calendar/reviews/{confirm_id}/confirm",
        json={"project_id": "prj_demo"},
    )
    assert confirmed.status_code == 200
    assert confirmed.json()["status"] == "resolved"
    assert confirmed.json()["resolved_by"] == "jonathan"

    dismissed = operations_client.post(
        f"/api/v1/integrations/calendar/reviews/{dismiss_id}/dismiss"
    )
    assert dismissed.status_code == 200
    assert dismissed.json()["status"] == "dismissed"
    assert operations_client.get("/api/v1/integrations/calendar/reviews").json() == []

    rerun = operations_client.post("/api/v1/integrations/calendar/sync", json=sync_payload())
    assert rerun.status_code == 200
    assert rerun.json()["created_count"] == 1
    assert session.query(Meeting).count() == 1


def test_failed_provider_run_is_redacted_and_retry_reuses_original_window(
    operations_client, registry
) -> None:
    failing = FailingCalendarAdapter()
    registry.register(source_system=SOURCE, external_scope=SCOPE, adapter=failing)

    response = operations_client.post("/api/v1/integrations/calendar/sync", json=sync_payload())
    assert response.status_code == 502
    run_id = response.json()["detail"]["run_id"]
    errors = operations_client.get(f"/api/v1/integrations/sync-runs/{run_id}/errors").json()
    assert errors[0]["code"] == "calendar_provider_error"
    assert errors[0]["message"] == "Authorization: [REDACTED]"
    assert "fictional-secret-token" not in str(errors)

    recovered = FakeCalendarAdapter([])
    registry.register(source_system=SOURCE, external_scope=SCOPE, adapter=recovered)
    retry = operations_client.post(f"/api/v1/integrations/sync-runs/{run_id}/retry")
    assert retry.status_code == 200
    assert retry.json()["retry_of_run_id"] == run_id
    assert retry.json()["status"] == "succeeded"
    assert recovered.windows == [CalendarWindow(starts_at=STARTS_AT, ends_at=ENDS_AT)]


def test_sync_window_is_bounded_and_successful_runs_cannot_be_retried(
    operations_client, registry
) -> None:
    registry.register(
        source_system=SOURCE,
        external_scope=SCOPE,
        adapter=FakeCalendarAdapter([]),
    )
    too_wide = sync_payload()
    too_wide["ends_at"] = (STARTS_AT + timedelta(days=32)).isoformat()
    response = operations_client.post("/api/v1/integrations/calendar/sync", json=too_wide)
    assert response.status_code == 409
    assert operations_client.get("/api/v1/integrations/sync-runs").json() == []

    success = operations_client.post(
        "/api/v1/integrations/calendar/sync", json=sync_payload()
    ).json()
    retry = operations_client.post(f"/api/v1/integrations/sync-runs/{success['run_id']}/retry")
    assert retry.status_code == 409
