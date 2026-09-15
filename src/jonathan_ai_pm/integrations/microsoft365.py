from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Protocol
from urllib.parse import quote, urlparse

import httpx

from jonathan_ai_pm.integrations.contracts import (
    READ_ONLY_CAPABILITIES,
    CalendarWindow,
    ExternalCalendarEvent,
    IntegrationCapabilities,
)
from jonathan_ai_pm.integrations.security import (
    require_read_only_capabilities,
    validate_microsoft_graph_permissions,
)

GRAPH_BASE_URL = "https://graph.microsoft.com/v1.0"
MICROSOFT_GRAPH_DELEGATED_PERMISSION = "Calendars.ReadBasic"


class Microsoft365CalendarError(RuntimeError):
    pass


class GraphResponse(Protocol):
    status_code: int

    def json(self) -> Any: ...


class GraphHttpClient(Protocol):
    def get(
        self,
        url: str,
        *,
        params: Mapping[str, str | int] | None,
        headers: Mapping[str, str],
        timeout: float,
    ) -> GraphResponse: ...


@dataclass(frozen=True, slots=True)
class Microsoft365CalendarConfig:
    calendar_id: str = "default"
    identity_scope: str | None = None
    page_size: int = 100
    max_pages: int = 100
    timeout_seconds: float = 15.0
    requested_permissions: tuple[str, ...] = (MICROSOFT_GRAPH_DELEGATED_PERMISSION,)

    def __post_init__(self) -> None:
        calendar_id = self.calendar_id.strip()
        identity_scope = self.identity_scope.strip() if self.identity_scope else calendar_id
        if not calendar_id:
            raise Microsoft365CalendarError("calendar_id cannot be empty")
        if not identity_scope:
            raise Microsoft365CalendarError("identity_scope cannot be empty")
        if isinstance(self.page_size, bool) or not 1 <= self.page_size <= 1000:
            raise Microsoft365CalendarError("page_size must be between 1 and 1000")
        if isinstance(self.max_pages, bool) or self.max_pages < 1:
            raise Microsoft365CalendarError("max_pages must be positive")
        if self.timeout_seconds <= 0:
            raise Microsoft365CalendarError("timeout_seconds must be positive")
        try:
            requested_permissions = validate_microsoft_graph_permissions(self.requested_permissions)
        except ValueError as exc:
            raise Microsoft365CalendarError(str(exc)) from exc
        object.__setattr__(self, "calendar_id", calendar_id)
        object.__setattr__(self, "identity_scope", identity_scope)
        object.__setattr__(self, "requested_permissions", requested_permissions)


class Microsoft365CalendarAdapter:
    """Read-only Microsoft Graph calendarView adapter using a delegated access token."""

    source_system = "microsoft-365"
    capabilities: IntegrationCapabilities = READ_ONLY_CAPABILITIES
    delegated_permission = MICROSOFT_GRAPH_DELEGATED_PERMISSION

    def __init__(
        self,
        token_provider: Callable[[], str],
        *,
        config: Microsoft365CalendarConfig | None = None,
        http_client: GraphHttpClient | None = None,
    ) -> None:
        self.token_provider = token_provider
        self.config = config or Microsoft365CalendarConfig()
        self.http_client = http_client or httpx
        self._enforce_read_only()

    def list_events(self, window: CalendarWindow) -> list[ExternalCalendarEvent]:
        self._enforce_read_only()
        try:
            supplied_token = self.token_provider()
        except Exception:
            raise Microsoft365CalendarError("Microsoft Graph access token is unavailable") from None
        if not isinstance(supplied_token, str) or not supplied_token.strip():
            raise Microsoft365CalendarError("Microsoft Graph access token is unavailable")
        token = supplied_token.strip()

        url = self._calendar_view_url()
        params: Mapping[str, str | int] | None = {
            "startDateTime": window.starts_at.isoformat(),
            "endDateTime": window.ends_at.isoformat(),
            "$top": self.config.page_size,
        }
        headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
            "Prefer": 'outlook.timezone="UTC"',
        }
        events: list[ExternalCalendarEvent] = []
        visited_urls: set[str] = set()

        for _page_number in range(1, self.config.max_pages + 1):
            if url in visited_urls:
                raise Microsoft365CalendarError("Microsoft Graph returned a pagination cycle")
            visited_urls.add(url)
            try:
                response = self.http_client.get(
                    url,
                    params=params,
                    headers=headers,
                    timeout=self.config.timeout_seconds,
                )
            except httpx.HTTPError:
                raise Microsoft365CalendarError(
                    "Microsoft Graph calendar request failed"
                ) from None
            if not 200 <= response.status_code < 300:
                raise Microsoft365CalendarError(
                    f"Microsoft Graph calendar request failed with HTTP {response.status_code}"
                )
            try:
                payload = response.json()
            except (TypeError, ValueError):
                raise Microsoft365CalendarError(
                    "Microsoft Graph returned an invalid calendar page"
                ) from None
            if not isinstance(payload, dict) or not isinstance(payload.get("value"), list):
                raise Microsoft365CalendarError("Microsoft Graph returned an invalid calendar page")
            events.extend(self._parse_event(item) for item in payload["value"])

            next_link = payload.get("@odata.nextLink")
            if next_link is None:
                return events
            url = _validated_next_link(next_link)
            params = None

        raise Microsoft365CalendarError("Microsoft Graph pagination exceeded the configured limit")

    def _enforce_read_only(self) -> None:
        try:
            require_read_only_capabilities(self.capabilities)
            validate_microsoft_graph_permissions(self.config.requested_permissions)
        except ValueError as exc:
            raise Microsoft365CalendarError(str(exc)) from exc

    def _calendar_view_url(self) -> str:
        if self.config.calendar_id == "default":
            return f"{GRAPH_BASE_URL}/me/calendar/calendarView"
        calendar_id = quote(self.config.calendar_id, safe="")
        return f"{GRAPH_BASE_URL}/me/calendars/{calendar_id}/calendarView"

    def _parse_event(self, payload: Any) -> ExternalCalendarEvent:
        if not isinstance(payload, dict):
            raise Microsoft365CalendarError("Microsoft Graph returned an invalid event")
        external_id = _required_string(payload.get("id"), "event.id")
        subject = payload.get("subject")
        title = (
            subject.strip() if isinstance(subject, str) and subject.strip() else "Untitled event"
        )
        last_modified = payload.get("lastModifiedDateTime")
        return ExternalCalendarEvent(
            source_system=self.source_system,
            calendar_id=str(self.config.identity_scope),
            external_id=external_id,
            title=title,
            starts_at=_parse_graph_datetime(payload.get("start"), "event.start"),
            ends_at=_parse_graph_datetime(payload.get("end"), "event.end"),
            status="cancelled" if payload.get("isCancelled") is True else "confirmed",
            web_url=_optional_string(payload.get("webLink")),
            last_modified_at=(
                _parse_iso_datetime(last_modified, "event.lastModifiedDateTime")
                if last_modified is not None
                else None
            ),
        )


def _validated_next_link(value: Any) -> str:
    if not isinstance(value, str):
        raise Microsoft365CalendarError("Microsoft Graph returned an invalid nextLink")
    parsed = urlparse(value)
    if parsed.scheme != "https" or parsed.hostname != "graph.microsoft.com":
        raise Microsoft365CalendarError("Microsoft Graph returned an untrusted nextLink")
    if not parsed.path.startswith("/v1.0/"):
        raise Microsoft365CalendarError("Microsoft Graph returned an unsupported nextLink")
    return value


def _required_string(value: Any, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise Microsoft365CalendarError(f"{field_name} cannot be empty")
    return value.strip()


def _optional_string(value: Any) -> str | None:
    return value.strip() if isinstance(value, str) and value.strip() else None


def _parse_graph_datetime(value: Any, field_name: str) -> datetime:
    if not isinstance(value, dict):
        raise Microsoft365CalendarError(f"{field_name} must be a dateTimeTimeZone object")
    raw = _required_string(value.get("dateTime"), f"{field_name}.dateTime")
    timezone_name = _required_string(value.get("timeZone"), f"{field_name}.timeZone")
    parsed = _from_isoformat(raw, f"{field_name}.dateTime")
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        if timezone_name.upper() not in {"UTC", "ETC/UTC"}:
            raise Microsoft365CalendarError(
                f"{field_name} was not returned in the requested UTC timezone"
            )
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _parse_iso_datetime(value: Any, field_name: str) -> datetime:
    raw = _required_string(value, field_name)
    parsed = _from_isoformat(raw, field_name)
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise Microsoft365CalendarError(f"{field_name} must include a timezone")
    return parsed.astimezone(UTC)


def _from_isoformat(value: str, field_name: str) -> datetime:
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise Microsoft365CalendarError(f"{field_name} is not a valid ISO 8601 timestamp") from exc
