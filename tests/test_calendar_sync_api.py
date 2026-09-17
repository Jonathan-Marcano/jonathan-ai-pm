from datetime import UTC, datetime


def _query(**params):
    return "&".join(f"{key}={value}" for key, value in params.items())


def test_calendar_sync_reports_not_configured_without_auth(api_client, session) -> None:
    query = _query(
        starts_at="2026-09-15T00:00:00%2B00%3A00",
        ends_at="2026-09-22T00:00:00%2B00%3A00",
    )
    response = api_client.post(f"/api/v1/integrations/calendar/sync?{query}")

    assert response.status_code == 503
    assert response.json()["detail"] == "Calendar integration is not configured"


def test_calendar_sync_rejects_naive_window(api_client, session) -> None:
    response = api_client.post(
        "/api/v1/integrations/calendar/sync"
        "?starts_at=2026-09-15T00:00:00&ends_at=2026-09-22T00:00:00"
    )

    assert response.status_code == 422


def test_calendar_sync_rejects_reversed_window(api_client, session) -> None:
    query = _query(
        starts_at="2026-09-22T00:00:00%2B00%3A00",
        ends_at="2026-09-15T00:00:00%2B00%3A00",
    )
    response = api_client.post(f"/api/v1/integrations/calendar/sync?{query}")

    assert response.status_code == 422


def test_calendar_sync_requires_the_window(api_client, session) -> None:
    query = _query(starts_at="2026-09-15T00:00:00%2B00%3A00")
    response = api_client.post(f"/api/v1/integrations/calendar/sync?{query}")

    assert response.status_code == 422


def test_reconciliation_uses_same_boundaries_for_google_calendar(session) -> None:
    from faroflow.integrations.contracts import (
        READ_ONLY_CAPABILITIES,
        CalendarWindow,
    )
    from faroflow.integrations.google_calendar import GoogleCalendarAdapter
    from faroflow.models import ExternalIdentity, Meeting, SyncRun
    from faroflow.services import DomainStore

    store = DomainStore(session)
    store.create("workspace", id="wrk_demo", name="Demo", timezone="America/Santiago")
    store.create("client", id="cli_demo", workspace_id="wrk_demo", name="Demo client")
    store.create("project", id="prj_demo", client_id="cli_demo", name="Demo project")

    class FakeHttpClient:
        def __init__(self, payload):
            self.payload = payload

        def get(self, url, *, params, headers, timeout):
            return FakeResponse(self.payload)

    class FakeResponse:
        status_code = 200

        def __init__(self, payload):
            self.payload = payload

        def json(self):
            return self.payload

    event = {
        "id": "gcal-1",
        "summary": "Demo sync",
        "start": {"dateTime": f"{datetime(2026, 9, 15, 16, tzinfo=UTC).isoformat()}"},
        "end": {"dateTime": f"{datetime(2026, 9, 15, 17, tzinfo=UTC).isoformat()}"},
        "status": "confirmed",
        "htmlLink": "https://calendar.google.com/calendar/event/gcal-1",
        "updated": "2026-09-14T19:30:00Z",
    }
    adapter = GoogleCalendarAdapter(
        lambda: "temporary-token",
        config=None,
        http_client=FakeHttpClient({"items": [event]}),
    )
    assert adapter.capabilities == READ_ONLY_CAPABILITIES

    from faroflow.integrations.reconciliation import reconcile_calendar_events

    run = reconcile_calendar_events(
        session,
        project_id="prj_demo",
        adapter=adapter,
        window=CalendarWindow(
            starts_at=datetime(2026, 9, 15, tzinfo=UTC),
            ends_at=datetime(2026, 9, 22, tzinfo=UTC),
        ),
    )

    assert run.status == "succeeded"
    assert run.created_count == 1
    assert session.query(Meeting).one().title == "Demo sync"
    assert session.query(ExternalIdentity).one().source_system == "google-calendar"
    assert session.query(ExternalIdentity).one().external_scope == "primary"
    assert session.query(SyncRun).count() == 1


def test_repeated_google_calendar_sync_is_idempotent(session) -> None:
    from faroflow.integrations.contracts import CalendarWindow
    from faroflow.integrations.google_calendar import GoogleCalendarAdapter
    from faroflow.integrations.reconciliation import reconcile_calendar_events
    from faroflow.models import Meeting
    from faroflow.services import DomainStore

    store = DomainStore(session)
    store.create("workspace", id="wrk_demo", name="Demo", timezone="America/Santiago")
    store.create("client", id="cli_demo", workspace_id="wrk_demo", name="Demo client")
    store.create("project", id="prj_demo", client_id="cli_demo", name="Demo project")

    event = {
        "id": "gcal-1",
        "summary": "Demo sync",
        "start": {"dateTime": "2026-09-15T16:00:00Z"},
        "end": {"dateTime": "2026-09-15T17:00:00Z"},
        "status": "confirmed",
        "htmlLink": "https://calendar.google.com/calendar/event/gcal-1",
        "updated": "2026-09-14T19:30:00Z",
    }

    def adapter():
        class FakeResponse:
            status_code = 200

            def json(self):
                return {"items": [event]}

        class FakeHttpClient:
            def get(self, url, *, params, headers, timeout):
                return FakeResponse()

        return GoogleCalendarAdapter(lambda: "temporary-token", http_client=FakeHttpClient())

    window = CalendarWindow(
        starts_at=datetime(2026, 9, 15, tzinfo=UTC),
        ends_at=datetime(2026, 9, 22, tzinfo=UTC),
    )
    def run():
        return reconcile_calendar_events(
            session,
            project_id="prj_demo",
            adapter=adapter(),
            window=window,
        )

    first = run()
    second = run()

    assert first.created_count == 1
    assert second.status == "succeeded"
    assert second.created_count == 0
    assert second.updated_count == 0
    assert second.unchanged_count == 1
    assert session.query(Meeting).count() == 1