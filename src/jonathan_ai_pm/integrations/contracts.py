from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Protocol


class IntegrationContractError(ValueError):
    pass


def _required_text(value: str, field_name: str) -> str:
    normalized = value.strip()
    if not normalized:
        raise IntegrationContractError(f"{field_name} cannot be empty")
    return normalized


def _as_utc(value: datetime, field_name: str) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise IntegrationContractError(f"{field_name} must include a timezone")
    return value.astimezone(UTC)


@dataclass(frozen=True, slots=True)
class IntegrationCapabilities:
    read: bool
    create: bool
    update: bool
    delete: bool


READ_ONLY_CAPABILITIES = IntegrationCapabilities(
    read=True,
    create=False,
    update=False,
    delete=False,
)


@dataclass(frozen=True, slots=True)
class CalendarWindow:
    starts_at: datetime
    ends_at: datetime

    def __post_init__(self) -> None:
        starts_at = _as_utc(self.starts_at, "starts_at")
        ends_at = _as_utc(self.ends_at, "ends_at")
        if starts_at >= ends_at:
            raise IntegrationContractError("Calendar window must end after it starts")
        object.__setattr__(self, "starts_at", starts_at)
        object.__setattr__(self, "ends_at", ends_at)


@dataclass(frozen=True, slots=True)
class ExternalCalendarEvent:
    source_system: str
    calendar_id: str
    external_id: str
    title: str
    starts_at: datetime
    ends_at: datetime
    status: str = "confirmed"
    web_url: str | None = None
    last_modified_at: datetime | None = None

    def __post_init__(self) -> None:
        source_system = _required_text(self.source_system, "source_system").lower()
        calendar_id = _required_text(self.calendar_id, "calendar_id")
        external_id = _required_text(self.external_id, "external_id")
        title = _required_text(self.title, "title")
        status = _required_text(self.status, "status").lower()
        starts_at = _as_utc(self.starts_at, "starts_at")
        ends_at = _as_utc(self.ends_at, "ends_at")
        if starts_at >= ends_at:
            raise IntegrationContractError("Calendar event must end after it starts")
        last_modified_at = (
            _as_utc(self.last_modified_at, "last_modified_at")
            if self.last_modified_at
            else None
        )
        object.__setattr__(self, "source_system", source_system)
        object.__setattr__(self, "calendar_id", calendar_id)
        object.__setattr__(self, "external_id", external_id)
        object.__setattr__(self, "title", title)
        object.__setattr__(self, "status", status)
        object.__setattr__(self, "starts_at", starts_at)
        object.__setattr__(self, "ends_at", ends_at)
        object.__setattr__(self, "last_modified_at", last_modified_at)

    @property
    def source_key(self) -> tuple[str, str, str]:
        return self.source_system, self.calendar_id, self.external_id


@dataclass(frozen=True, slots=True)
class ExternalDocumentMetadata:
    source_system: str
    external_id: str
    name: str
    web_url: str
    mime_type: str | None = None
    last_modified_at: datetime | None = None
    etag: str | None = None

    def __post_init__(self) -> None:
        source_system = _required_text(self.source_system, "source_system").lower()
        external_id = _required_text(self.external_id, "external_id")
        name = _required_text(self.name, "name")
        web_url = _required_text(self.web_url, "web_url")
        last_modified_at = (
            _as_utc(self.last_modified_at, "last_modified_at")
            if self.last_modified_at
            else None
        )
        object.__setattr__(self, "source_system", source_system)
        object.__setattr__(self, "external_id", external_id)
        object.__setattr__(self, "name", name)
        object.__setattr__(self, "web_url", web_url)
        object.__setattr__(self, "last_modified_at", last_modified_at)

    @property
    def source_key(self) -> tuple[str, str]:
        return self.source_system, self.external_id


class ReadOnlyCalendarAdapter(Protocol):
    source_system: str
    capabilities: IntegrationCapabilities

    def list_events(self, window: CalendarWindow) -> list[ExternalCalendarEvent]: ...


class ReadOnlyDocumentAdapter(Protocol):
    source_system: str
    capabilities: IntegrationCapabilities

    def get_metadata(self, external_id: str) -> ExternalDocumentMetadata: ...
