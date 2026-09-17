from datetime import UTC, datetime, timedelta

from faroflow.integrations.contracts import (
    READ_ONLY_CAPABILITIES,
    CalendarWindow,
    ExternalCalendarEvent,
)
from faroflow.integrations.persistence import IntegrationStateStore
from faroflow.integrations.reconciliation import (
    reconcile_calendar_events,
    reconcile_drive_files,
)
from faroflow.models import SyncRun
from faroflow.services import DomainStore

START = datetime(2026, 9, 17, 9, 0, tzinfo=UTC)
WINDOW = CalendarWindow(starts_at=START, ends_at=START + timedelta(days=7))


class FakedCalendarAdapter:
    source_system = "mocked-365"
    capabilities = READ_ONLY_CAPABILITIES

    def list_events(self, window: CalendarWindow) -> list[ExternalCalendarEvent]:
        return [
            ExternalCalendarEvent(
                source_system="mocked-365",
                calendar_id="work",
                external_id="evt-1",
                title="Standup",
                starts_at=WINDOW.starts_at + timedelta(hours=1),
                ends_at=WINDOW.starts_at + timedelta(hours=2),
            )
        ]


class FakedDriveAdapter:
    source_system = "google-drive"
    capabilities = READ_ONLY_CAPABILITIES

    def get_metadata(self, external_id: str):
        from faroflow.integrations.contracts import ExternalDocumentMetadata

        return ExternalDocumentMetadata(
            source_system="google-drive",
            external_id=external_id,
            name="Plan.pdf",
            web_url=f"https://drive.example.test/{external_id}",
            mime_type="application/pdf",
        )


def build_project(session) -> None:
    store = DomainStore(session)
    store.create("workspace", id="wrk_demo", name="Demo", timezone="America/Santiago")
    store.create("client", id="cli_demo", workspace_id="wrk_demo", name="Demo client")
    store.create("project", id="prj_demo", client_id="cli_demo", name="Demo project")
    store.create(
        "deliverable",
        id="dlv_demo",
        project_id="prj_demo",
        title="Project plan",
        due_at=datetime(2026, 9, 30, tzinfo=UTC).date(),
    )


def seed_runs(session) -> list[SyncRun]:
    build_project(session)
    store = DomainStore(session)
    run = reconcile_calendar_events(
        session, project_id="prj_demo", adapter=FakedCalendarAdapter(), window=WINDOW
    )
    store.link_drive_file(
        "dlv_demo",
        source_system="google-drive",
        external_id="file-1",
        name="Plan.pdf",
        web_url="https://drive.example.test/file-1",
    )
    drive_run = reconcile_drive_files(session, adapter=FakedDriveAdapter())
    return [run, drive_run]


def test_list_sync_runs_with_filters(api_client, session) -> None:
    calendar_run, drive_run = seed_runs(session)

    response = api_client.get(
        "/api/v1/integrations/sync-runs?source_system=mocked-365&status=succeeded"
    )

    assert response.status_code == 200
    assert [item["id"] for item in response.json()] == [calendar_run.id]

    all_runs = api_client.get("/api/v1/integrations/sync-runs?limit=1")
    assert all_runs.status_code == 200
    assert len(all_runs.json()) == 1
    assert all_runs.headers["link"] is not None


def test_get_sync_run_detail(api_client, session) -> None:
    calendar_run, _drive_run = seed_runs(session)

    response = api_client.get(f"/api/v1/integrations/sync-runs/{calendar_run.id}")

    assert response.status_code == 200
    body = response.json()
    assert body["id"] == calendar_run.id
    assert body["resource_kind"] == "calendar"
    assert body["status"] == "succeeded"
    assert body["created_count"] == 1
    assert body["window_starts_at"] is not None


def test_sync_run_errors_and_redaction(api_client, session) -> None:
    build_project(session)
    store = DomainStore(session)
    state = IntegrationStateStore(session)
    run = state.start_run(
        source_system="mocked-365",
        resource_kind="calendar",
        window_starts_at=WINDOW.starts_at,
        window_ends_at=WINDOW.ends_at,
    )
    store.link_drive_file(
        "dlv_demo",
        source_system="google-drive",
        external_id="file-1",
        name="Plan.pdf",
        web_url="https://drive.example.test/file-1",
    )
    state.record_error(
        run.id,
        code="list_failed",
        message="Google token Bearer sk-abcdef1234 failed to refresh",
    )
    state.finish_run(run.id, seen_count=0, status="failed")

    response = api_client.get(f"/api/v1/integrations/sync-runs/{run.id}/errors")

    assert response.status_code == 200
    body = response.json()
    assert body[0]["code"] == "list_failed"
    assert "sk-abcdef1234" not in body[0]["message"]
    assert "[REDACTED]" in body[0]["message"]


def test_unknown_sync_run_is_404(api_client, session) -> None:
    detail = api_client.get("/api/v1/integrations/sync-runs/syn_absent")
    assert detail.status_code == 404
    errors = api_client.get("/api/v1/integrations/sync-runs/syn_absent/errors")
    assert errors.status_code == 404
    retry = api_client.post("/api/v1/integrations/sync-runs/syn_absent/retry")
    assert retry.status_code == 404


def test_retry_reuses_saved_calendar_window(api_client, session) -> None:
    calendar_run, _drive_run = seed_runs(session)

    response = api_client.post(f"/api/v1/integrations/sync-runs/{calendar_run.id}/retry")

    assert response.status_code == 503


def test_retry_of_drive_run(session, api_client) -> None:
    _calendar_run, drive_run = seed_runs(session)

    response = api_client.post(f"/api/v1/integrations/sync-runs/{drive_run.id}/retry")

    assert response.status_code == 503