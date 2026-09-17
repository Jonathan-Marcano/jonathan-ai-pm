from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Protocol
from urllib.parse import quote

import httpx

from faroflow.integrations.contracts import (
    READ_ONLY_CAPABILITIES,
    CalendarWindow,
    ExternalCalendarEvent,
    IntegrationCapabilities,
)

GOOGLE_CALENDAR_BASE_URL = "https://www.googleapis.com/calendar/v3"
GOOGLE_CALENDAR_DELEGATED_SCOPE = "https://www.googleapis.com/auth/calendar.readonly"
UNTITLED_EVENT_TITLE = "Untitled event"


class GoogleCalendarError(RuntimeError):
    pass


class GoogleCalendarNotConfigured(GoogleCalendarError):
    pass


class CalendarResponse(Protocol):
    status_code: int

    def json(self) -> Any: ...


class CalendarHttpClient(Protocol):
    def get(
        self,
        url: str,
        *,
        params: Mapping[str, str | int] | None,
        headers: Mapping[str, str],
        timeout: float,
    ) -> CalendarResponse: ...


@dataclass(frozen=True, slots=True)
class GoogleCalendarConfig:
    calendar_id: str = "primary"
    identity_scope: str | None = None
    page_size: int = 100
    max_pages: int = 100
    timeout_seconds: float = 15.0

    def __post_init__(self) -> None:
        calendar_id = self.calendar_id.strip()
        identity_scope = self.identity_scope.strip() if self.identity_scope else calendar_id
        if not calendar_id:
            raise GoogleCalendarError("calendar_id cannot be empty")
        if not identity_scope:
            raise GoogleCalendarError("identity_scope cannot be empty")
        if isinstance(self.page_size, bool) or not 1 <= self.page_size <= 1000:
            raise GoogleCalendarError("page_size must be between 1 and 1000")
        if isinstance(self.max_pages, bool) or self.max_pages < 1:
            raise GoogleCalendarError("max_pages must be positive")
        if self.timeout_seconds <= 0:
            raise GoogleCalendarError("timeout_seconds must be positive")
        object.__setattr__(self, "calendar_id", calendar_id)
        object.__setattr__(self, "identity_scope", identity_scope)


class GoogleCalendarAdapter:
    """Read-only Google Calendar events adapter using a delegated access token.

    Fetches bounded UTC event lists only. It never retrieves event bodies, attachments, or
    extensions, and never issues provider writes.
    """

    source_system = "google-calendar"
    capabilities: IntegrationCapabilities = READ_ONLY_CAPABILITIES
    delegated_scope = GOOGLE_CALENDAR_DELEGATED_SCOPE

    def __init__(
        self,
        token_provider: Callable[[], str],
        *,
        config: GoogleCalendarConfig | None = None,
        http_client: CalendarHttpClient | None = None,
    ) -> None:
        self.token_provider = token_provider
        self.config = config or GoogleCalendarConfig()
        self.http_client = http_client or httpx

    def list_events(self, window: CalendarWindow) -> list[ExternalCalendarEvent]:
        try:
            supplied_token = self.token_provider()
        except Exception:
            raise GoogleCalendarError("Google Calendar access token is unavailable") from None
        if not isinstance(supplied_token, str) or not supplied_token.strip():
            raise GoogleCalendarError("Google Calendar access token is unavailable")
        token = supplied_token.strip()

        calendar = quote(self.config.calendar_id, safe="")
        url = f"{GOOGLE_CALENDAR_BASE_URL}/calendars/{calendar}/events"
        base_params: Mapping[str, str | int] = {
            "timeMin": window.starts_at.isoformat(),
            "timeMax": window.ends_at.isoformat(),
            "timeZone": "UTC",
            "singleEvents": "true",
            "maxResults": self.config.page_size,
        }
        headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
        }
        events: list[ExternalCalendarEvent] = []
        visited_tokens: set[str] = set()
        page_token: str | None = None

        for _page_number in range(1, self.config.max_pages + 1):
            if page_token is not None and page_token in visited_tokens:
                raise GoogleCalendarError("Google Calendar returned a pagination cycle")
            if page_token is not None:
                visited_tokens.add(page_token)
            params = (
                base_params
                if page_token is None
                else {**base_params, "pageToken": page_token}
            )
            try:
                response = self.http_client.get(
                    url,
                    params=params,
                    headers=headers,
                    timeout=self.config.timeout_seconds,
                )
            except httpx.HTTPError:
                raise GoogleCalendarError("Google Calendar request failed") from None
            if not 200 <= response.status_code < 300:
                raise GoogleCalendarError(
                    f"Google Calendar request failed with HTTP {response.status_code}"
                )
            try:
                payload = response.json()
            except (TypeError, ValueError):
                raise GoogleCalendarError("Google Calendar returned an invalid page") from None
            if not isinstance(payload, dict) or not isinstance(payload.get("items"), list):
                raise GoogleCalendarError("Google Calendar returned an invalid page")
            events.extend(self._parse_event(item) for item in payload["items"])

            page_token = payload.get("nextPageToken")
            if page_token is None:
                return events
            if not isinstance(page_token, str) or not page_token.strip():
                raise GoogleCalendarError("Google Calendar returned an invalid nextPageToken")

        raise GoogleCalendarError("Google Calendar pagination exceeded the configured limit")

    def _parse_event(self, payload: Any) -> ExternalCalendarEvent:
        if not isinstance(payload, dict):
            raise GoogleCalendarError("Google Calendar returned an invalid event")
        external_id = _required_string(payload.get("id"), "event.id")
        summary = payload.get("summary")
        title = (
            summary.strip()
            if isinstance(summary, str) and summary.strip()
            else UNTITLED_EVENT_TITLE
        )
        starts_at = _parse_datetime_field(payload.get("start"), "event.start")
        ends_at = _parse_datetime_field(payload.get("end"), "event.end")
        raw_status = _required_string(payload.get("status"), "event.status").lower()
        updated = payload.get("updated")
        return ExternalCalendarEvent(
            source_system=self.source_system,
            calendar_id=str(self.config.identity_scope),
            external_id=external_id,
            title=title,
            starts_at=starts_at,
            ends_at=ends_at,
            status="cancelled" if raw_status == "cancelled" else "confirmed",
            web_url=_optional_string(payload.get("htmlLink")),
            last_modified_at=(
                _parse_iso_datetime(updated, "event.updated")
                if updated is not None
                else None
            ),
        )


def build_google_calendar_adapter() -> GoogleCalendarAdapter:
    """Build the runtime adapter once tenant authorization is supplied.

    Tenant authorization is not configured yet, so this helper intentionally raises
    ``GoogleCalendarNotConfigured``. The endpoint exposes that state as HTTP 503.
    """
    raise GoogleCalendarNotConfigured("Calendar integration is not configured")


def _required_string(value: Any, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise GoogleCalendarError(f"{field_name} cannot be empty")
    return value.strip()


def _optional_string(value: Any) -> str | None:
    return value.strip() if isinstance(value, str) and value.strip() else None


def _parse_datetime_field(value: Any, field_name: str) -> datetime:
    if not isinstance(value, dict):
        raise GoogleCalendarError(f"{field_name} must be an object")
    raw = value.get("dateTime")
    if not isinstance(raw, str) or not raw.strip():
        raise GoogleCalendarError(f"{field_name} must include a dateTime")
    parsed = _from_isoformat(raw.strip(), f"{field_name}.dateTime")
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise GoogleCalendarError(f"{field_name}.dateTime must include a timezone")
    return parsed.astimezone(UTC)


def _parse_iso_datetime(value: Any, field_name: str) -> datetime:
    raw = _required_string(value, field_name)
    parsed = _from_isoformat(raw, field_name)
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise GoogleCalendarError(f"{field_name} must include a timezone")
    return parsed.astimezone(UTC)


def _from_isoformat(value: str, field_name: str) -> datetime:
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise GoogleCalendarError(f"{field_name} is not a valid ISO 8601 timestamp") from exc