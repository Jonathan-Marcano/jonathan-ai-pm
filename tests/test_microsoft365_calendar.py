from datetime import UTC, datetime

import httpx
import pytest

from jonathan_ai_pm.integrations import (
    MICROSOFT_GRAPH_DELEGATED_PERMISSION,
    READ_ONLY_CAPABILITIES,
    CalendarWindow,
    Microsoft365CalendarAdapter,
    Microsoft365CalendarConfig,
    Microsoft365CalendarError,
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


def graph_event(event_id="event-123", subject="Client review"):
    return {
        "id": event_id,
        "subject": subject,
        "start": {"dateTime": "2026-09-15T16:00:00.0000000", "timeZone": "UTC"},
        "end": {"dateTime": "2026-09-15T17:00:00.0000000", "timeZone": "UTC"},
        "isCancelled": False,
        "webLink": f"https://outlook.office.com/calendar/item/{event_id}",
        "lastModifiedDateTime": "2026-09-14T19:30:00Z",
    }


def test_adapter_requests_bounded_default_calendar_view() -> None:
    client = FakeHttpClient(FakeResponse({"value": [graph_event()]}))
    adapter = Microsoft365CalendarAdapter(
        lambda: "temporary-token",
        config=Microsoft365CalendarConfig(identity_scope="cisco:default", page_size=50),
        http_client=client,
    )

    events = adapter.list_events(calendar_window())

    assert len(events) == 1
    assert events[0].source_key == ("microsoft-365", "cisco:default", "event-123")
    assert events[0].starts_at == datetime(2026, 9, 15, 16, 0, tzinfo=UTC)
    call = client.calls[0]
    assert call["url"] == "https://graph.microsoft.com/v1.0/me/calendar/calendarView"
    assert call["params"] == {
        "startDateTime": "2026-09-15T00:00:00+00:00",
        "endDateTime": "2026-09-22T00:00:00+00:00",
        "$top": 50,
    }
    assert call["headers"]["Prefer"] == 'outlook.timezone="UTC"'
    assert call["headers"]["Authorization"] == "Bearer temporary-token"


def test_adapter_uses_configured_calendar_and_follows_next_link() -> None:
    next_link = (
        "https://graph.microsoft.com/v1.0/me/calendars/work/calendarView?$skiptoken=fictional"
    )
    client = FakeHttpClient(
        FakeResponse({"value": [graph_event("event-1")], "@odata.nextLink": next_link}),
        FakeResponse({"value": [graph_event("event-2", "Second review")]}),
    )
    adapter = Microsoft365CalendarAdapter(
        lambda: "temporary-token",
        config=Microsoft365CalendarConfig(
            calendar_id="calendar / work",
            identity_scope="stefanini:work",
        ),
        http_client=client,
    )

    events = adapter.list_events(calendar_window())

    assert [event.external_id for event in events] == ["event-1", "event-2"]
    assert client.calls[0]["url"].endswith("/calendars/calendar%20%2F%20work/calendarView")
    assert client.calls[1]["url"] == next_link
    assert client.calls[1]["params"] is None


def test_adapter_maps_cancelled_and_untitled_events() -> None:
    event = graph_event(subject="   ")
    event["isCancelled"] = True
    client = FakeHttpClient(FakeResponse({"value": [event]}))

    result = Microsoft365CalendarAdapter(lambda: "temporary-token", http_client=client).list_events(
        calendar_window()
    )

    assert result[0].title == "Untitled event"
    assert result[0].status == "cancelled"


def test_adapter_rejects_untrusted_or_cyclic_pagination() -> None:
    untrusted = FakeHttpClient(
        FakeResponse(
            {
                "value": [],
                "@odata.nextLink": "https://attacker.example/steal-pagination-token",
            }
        )
    )
    with pytest.raises(Microsoft365CalendarError, match="untrusted"):
        Microsoft365CalendarAdapter(lambda: "temporary-token", http_client=untrusted).list_events(
            calendar_window()
        )

    first_url = "https://graph.microsoft.com/v1.0/me/calendar/calendarView"
    cyclic = FakeHttpClient(FakeResponse({"value": [], "@odata.nextLink": first_url}))
    with pytest.raises(Microsoft365CalendarError, match="cycle"):
        Microsoft365CalendarAdapter(lambda: "temporary-token", http_client=cyclic).list_events(
            calendar_window()
        )


def test_adapter_rejects_non_utc_naive_response_and_invalid_pages() -> None:
    event = graph_event()
    event["start"]["timeZone"] = "Pacific Standard Time"
    client = FakeHttpClient(FakeResponse({"value": [event]}))
    with pytest.raises(Microsoft365CalendarError, match="requested UTC"):
        Microsoft365CalendarAdapter(lambda: "temporary-token", http_client=client).list_events(
            calendar_window()
        )

    invalid = FakeHttpClient(FakeResponse({"items": []}))
    with pytest.raises(Microsoft365CalendarError, match="invalid calendar page"):
        Microsoft365CalendarAdapter(lambda: "temporary-token", http_client=invalid).list_events(
            calendar_window()
        )


def test_adapter_exposes_only_least_privilege_read_capability() -> None:
    assert MICROSOFT_GRAPH_DELEGATED_PERMISSION == "Calendars.ReadBasic"
    assert Microsoft365CalendarAdapter.capabilities == READ_ONLY_CAPABILITIES
    assert Microsoft365CalendarAdapter.capabilities.create is False
    assert Microsoft365CalendarAdapter.capabilities.update is False
    assert Microsoft365CalendarAdapter.capabilities.delete is False


def test_adapter_errors_do_not_echo_token_or_provider_payload() -> None:
    token = "highly-sensitive-token"
    client = FakeHttpClient(
        FakeResponse({"error": {"message": f"Authorization: Bearer {token}"}}, status_code=401)
    )
    with pytest.raises(Microsoft365CalendarError) as captured:
        Microsoft365CalendarAdapter(lambda: token, http_client=client).list_events(
            calendar_window()
        )

    assert "401" in str(captured.value)
    assert token not in str(captured.value)
    assert "Authorization" not in str(captured.value)


def test_adapter_wraps_network_errors_without_exposing_token() -> None:
    token = "highly-sensitive-token"
    with pytest.raises(Microsoft365CalendarError) as captured:
        Microsoft365CalendarAdapter(lambda: token, http_client=FailingHttpClient()).list_events(
            calendar_window()
        )

    assert str(captured.value) == "Microsoft Graph calendar request failed"
    assert token not in str(captured.value)
    assert captured.value.__cause__ is None


def test_default_config_is_valid() -> None:
    assert Microsoft365CalendarConfig().calendar_id == "default"


def test_config_rejects_unsafe_limits() -> None:
    with pytest.raises(Microsoft365CalendarError, match="between 1 and 1000"):
        Microsoft365CalendarConfig(page_size=1001)
    with pytest.raises(Microsoft365CalendarError, match="max_pages"):
        Microsoft365CalendarConfig(max_pages=0)
    with pytest.raises(Microsoft365CalendarError, match="timeout_seconds"):
        Microsoft365CalendarConfig(timeout_seconds=0)
