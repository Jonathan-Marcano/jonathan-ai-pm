from datetime import UTC, datetime

import httpx
import pytest

from faroflow.integrations import (
    GOOGLE_CALENDAR_DELEGATED_SCOPE,
    READ_ONLY_CAPABILITIES,
    CalendarWindow,
    GoogleCalendarAdapter,
    GoogleCalendarConfig,
    GoogleCalendarError,
)


class FakeResponse:
    def __init__(self, payload, status_code=200):
        self.payload = payload
        self.status_code = status_code

    def json(self):
        return self.payload


class FakeHttpClient:
    def __init__(self, *responses):
        self.responses = list(responses)
        self.calls = []

    def get(self, url, *, params, headers, timeout):
        self.calls.append({"url": url, "params": params, "headers": headers, "timeout": timeout})
        return self.responses.pop(0)


class FailingHttpClient:
    def get(self, url, *, params, headers, timeout):
        request = httpx.Request("GET", url)
        raise httpx.ConnectError("fictional network failure", request=request)


def calendar_window() -> CalendarWindow:
    return CalendarWindow(
        starts_at=datetime(2026, 9, 15, 0, 0, tzinfo=UTC),
        ends_at=datetime(2026, 9, 22, 0, 0, tzinfo=UTC),
    )


def calendar_event(event_id="event-123", summary="Client review"):
    return {
        "id": event_id,
        "summary": summary,
        "start": {"dateTime": "2026-09-15T16:00:00Z"},
        "end": {"dateTime": "2026-09-15T17:00:00Z"},
        "status": "confirmed",
        "htmlLink": f"https://calendar.google.com/calendar/event/{event_id}",
        "updated": "2026-09-14T19:30:00Z",
    }


def test_adapter_requests_bounded_default_calendar() -> None:
    client = FakeHttpClient(FakeResponse({"items": [calendar_event()]}))
    adapter = GoogleCalendarAdapter(
        lambda: "temporary-token",
        config=GoogleCalendarConfig(identity_scope="acme:default", page_size=50),
        http_client=client,
    )

    events = adapter.list_events(calendar_window())

    assert len(events) == 1
    assert events[0].source_key == ("google-calendar", "acme:default", "event-123")
    assert events[0].starts_at == datetime(2026, 9, 15, 16, 0, tzinfo=UTC)
    call = client.calls[0]
    assert call["url"].endswith("/calendars/primary/events")
    assert call["params"]["timeMin"] == "2026-09-15T00:00:00+00:00"
    assert call["params"]["timeMax"] == "2026-09-22T00:00:00+00:00"
    assert call["params"]["timeZone"] == "UTC"
    assert call["params"]["singleEvents"] == "true"
    assert call["params"]["maxResults"] == 50
    assert call["headers"]["Authorization"] == "Bearer temporary-token"


def test_adapter_uses_configured_calendar_and_follows_page_token() -> None:
    client = FakeHttpClient(
        FakeResponse({"items": [calendar_event("event-1")], "nextPageToken": "tok-2"}),
        FakeResponse({"items": [calendar_event("event-2", "Second review")]}),
    )
    adapter = GoogleCalendarAdapter(
        lambda: "temporary-token",
        config=GoogleCalendarConfig(
            calendar_id="calendar / work",
            identity_scope="acme:work",
        ),
        http_client=client,
    )

    events = adapter.list_events(calendar_window())

    assert [event.external_id for event in events] == ["event-1", "event-2"]
    assert client.calls[0]["url"].endswith("/calendars/calendar%20%2F%20work/events")
    assert client.calls[1]["params"]["pageToken"] == "tok-2"


def test_adapter_maps_cancelled_tentative_and_untitled_events() -> None:
    cancelled = calendar_event(summary="   ")
    cancelled["status"] = "cancelled"
    tentative = calendar_event("event-2")
    tentative["status"] = "tentative"
    client = FakeHttpClient(FakeResponse({"items": [cancelled, tentative]}))

    events = GoogleCalendarAdapter(lambda: "temporary-token", http_client=client).list_events(
        calendar_window()
    )

    assert [event.title for event in events] == ["Untitled event", "Client review"]
    assert [event.status for event in events] == ["cancelled", "confirmed"]


def test_adapter_rejects_cyclic_or_excessive_pagination() -> None:
    cyclic = FakeHttpClient(
        FakeResponse({"items": [], "nextPageToken": "tok"}),
        FakeResponse({"items": [], "nextPageToken": "tok"}),
    )
    with pytest.raises(GoogleCalendarError, match="cycle"):
        GoogleCalendarAdapter(lambda: "temporary-token", http_client=cyclic).list_events(
            calendar_window()
        )

    with pytest.raises(GoogleCalendarError, match="exceeded"):
        GoogleCalendarAdapter(
            lambda: "temporary-token",
            config=GoogleCalendarConfig(max_pages=1),
            http_client=FakeHttpClient(FakeResponse({"items": [], "nextPageToken": "tok"})),
        ).list_events(calendar_window())


def test_adapter_rejects_naive_all_day_and_invalid_pages() -> None:
    event = calendar_event()
    event["start"]["dateTime"] = "2026-09-15T16:00:00"
    response = FakeResponse({"items": [event]})
    adapter = GoogleCalendarAdapter(lambda: "temporary-token", http_client=FakeHttpClient(response))
    with pytest.raises(GoogleCalendarError, match="timezone"):
        adapter.list_events(calendar_window())

    all_day = calendar_event()
    all_day["start"] = {"date": "2026-09-15"}
    all_day["end"] = {"date": "2026-09-16"}
    response = FakeResponse({"items": [all_day]})
    adapter = GoogleCalendarAdapter(lambda: "temporary-token", http_client=FakeHttpClient(response))
    with pytest.raises(GoogleCalendarError, match="dateTime"):
        adapter.list_events(calendar_window())

    response = FakeResponse({"events": []})
    adapter = GoogleCalendarAdapter(lambda: "temporary-token", http_client=FakeHttpClient(response))
    with pytest.raises(GoogleCalendarError, match="invalid page"):
        adapter.list_events(calendar_window())


def test_adapter_exposes_only_least_privilege_read_capability() -> None:
    assert GOOGLE_CALENDAR_DELEGATED_SCOPE == "https://www.googleapis.com/auth/calendar.readonly"
    assert GoogleCalendarAdapter.capabilities == READ_ONLY_CAPABILITIES
    assert GoogleCalendarAdapter.capabilities.create is False
    assert GoogleCalendarAdapter.capabilities.update is False
    assert GoogleCalendarAdapter.capabilities.delete is False


def test_adapter_errors_do_not_echo_token_or_provider_payload() -> None:
    token = "highly-sensitive-token"
    client = FakeHttpClient(
        FakeResponse(
            {"error": {"message": f"Authorization: Bearer {token}"}},
            status_code=401,
        )
    )
    with pytest.raises(GoogleCalendarError) as captured:
        GoogleCalendarAdapter(lambda: token, http_client=client).list_events(calendar_window())

    assert "401" in str(captured.value)
    assert token not in str(captured.value)
    assert "Authorization" not in str(captured.value)


def test_adapter_wraps_network_errors_without_exposing_token() -> None:
    token = "highly-sensitive-token"
    with pytest.raises(GoogleCalendarError) as captured:
        GoogleCalendarAdapter(lambda: token, http_client=FailingHttpClient()).list_events(
            calendar_window()
        )

    assert str(captured.value) == "Google Calendar request failed"
    assert token not in str(captured.value)
    assert captured.value.__cause__ is None


def test_default_config_is_valid() -> None:
    assert GoogleCalendarConfig().calendar_id == "primary"
    assert GoogleCalendarConfig().identity_scope == "primary"


def test_config_rejects_unsafe_limits() -> None:
    with pytest.raises(GoogleCalendarError, match="between 1 and 1000"):
        GoogleCalendarConfig(page_size=1001)
    with pytest.raises(GoogleCalendarError, match="max_pages"):
        GoogleCalendarConfig(max_pages=0)
    with pytest.raises(GoogleCalendarError, match="timeout_seconds"):
        GoogleCalendarConfig(timeout_seconds=0)