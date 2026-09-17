from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Protocol
from urllib.parse import quote

import httpx

from faroflow.integrations.contracts import (
    READ_ONLY_CAPABILITIES,
    ExternalDocumentMetadata,
    IntegrationCapabilities,
)

DRIVE_BASE_URL = "https://www.googleapis.com/drive/v3/files"
DRIVE_DELEGATED_SCOPE = "https://www.googleapis.com/auth/drive.metadata.readonly"
DRIVE_METADATA_FIELDS = "id,name,webViewLink,mimeType,modifiedTime,version"


class GoogleDriveError(RuntimeError):
    pass


class GoogleDriveNotConfigured(GoogleDriveError):
    pass


class DriveResponse(Protocol):
    status_code: int

    def json(self) -> Any: ...


class DriveHttpClient(Protocol):
    def get(
        self,
        url: str,
        *,
        params: Mapping[str, str | int] | None,
        headers: Mapping[str, str],
        timeout: float,
    ) -> DriveResponse: ...


@dataclass(frozen=True, slots=True)
class GoogleDriveConfig:
    timeout_seconds: float = 15.0

    def __post_init__(self) -> None:
        if self.timeout_seconds <= 0:
            raise GoogleDriveError("timeout_seconds must be positive")


class GoogleDriveAdapter:
    """Read-only Google Drive metadata adapter using a delegated access token.

    Fetches file metadata only (id, name, web link, MIME type, modification time, and version
    marker). It never retrieves file content and never issues provider writes.
    """

    source_system = "google-drive"
    capabilities: IntegrationCapabilities = READ_ONLY_CAPABILITIES
    delegated_scope = DRIVE_DELEGATED_SCOPE

    def __init__(
        self,
        token_provider: Callable[[], str],
        *,
        config: GoogleDriveConfig | None = None,
        http_client: DriveHttpClient | None = None,
    ) -> None:
        self.token_provider = token_provider
        self.config = config or GoogleDriveConfig()
        self.http_client = http_client or httpx

    def get_metadata(self, external_id: str) -> ExternalDocumentMetadata:
        try:
            supplied_token = self.token_provider()
        except Exception:
            raise GoogleDriveError("Drive access token is unavailable") from None
        if not isinstance(supplied_token, str) or not supplied_token.strip():
            raise GoogleDriveError("Drive access token is unavailable")
        token = supplied_token.strip()

        header = {"Authorization": f"Bearer {token}", "Accept": "application/json"}
        params: Mapping[str, str | int] = {
            "fields": DRIVE_METADATA_FIELDS,
            "alt": "json",
            "supportsAllDrives": "true",
        }
        url = f"{DRIVE_BASE_URL}/{quote(external_id.strip(), safe='')}"
        try:
            response = self.http_client.get(
                url,
                params=params,
                headers=header,
                timeout=self.config.timeout_seconds,
            )
        except httpx.HTTPError:
            raise GoogleDriveError("Google Drive metadata request failed") from None
        if not 200 <= response.status_code < 300:
            raise GoogleDriveError(
                f"Google Drive metadata request failed with HTTP {response.status_code}"
            )
        try:
            payload = response.json()
        except (TypeError, ValueError):
            raise GoogleDriveError("Google Drive returned invalid metadata") from None
        return _parse_drive_metadata(self.source_system, payload)


def build_google_drive_adapter() -> GoogleDriveAdapter:
    """Build the runtime adapter once tenant authorization is supplied.

    Tenant authorization is not configured yet, so this helper intentionally raises
    ``GoogleDriveNotConfigured``. The endpoint exposes that state as HTTP 503.
    """
    raise GoogleDriveNotConfigured("Drive integration is not configured")


def _parse_drive_metadata(source_system: str, payload: Any) -> ExternalDocumentMetadata:
    if not isinstance(payload, dict):
        raise GoogleDriveError("Google Drive returned invalid metadata")
    external_id = _required_string(payload.get("id"), "file.id")
    name = _required_string(payload.get("name"), "file.name")
    web_url = _required_string(payload.get("webViewLink"), "file.webViewLink")
    version = payload.get("version")
    modified_time = payload.get("modifiedTime")
    return ExternalDocumentMetadata(
        source_system=source_system,
        external_id=external_id,
        name=name,
        web_url=web_url,
        mime_type=_optional_string(payload.get("mimeType")),
        etag=str(version) if version is not None else None,
        last_modified_at=(
            _parse_iso_datetime(modified_time, "file.modifiedTime")
            if modified_time is not None
            else None
        ),
    )


def _required_string(value: Any, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise GoogleDriveError(f"{field_name} cannot be empty")
    return value.strip()


def _optional_string(value: Any) -> str | None:
    return value.strip() if isinstance(value, str) and value.strip() else None


def _parse_iso_datetime(value: Any, field_name: str) -> datetime:
    raw = _required_string(value, field_name)
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError as exc:
        raise GoogleDriveError(f"{field_name} is not a valid ISO 8601 timestamp") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise GoogleDriveError(f"{field_name} must include a timezone")
    return parsed.astimezone(UTC)