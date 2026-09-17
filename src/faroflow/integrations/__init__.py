"""Provider-neutral Phase 2 integration contracts."""

from faroflow.integrations.contracts import (
    READ_ONLY_CAPABILITIES,
    CalendarWindow,
    ExternalCalendarEvent,
    ExternalDocumentMetadata,
    IntegrationCapabilities,
    IntegrationContractError,
    ReadOnlyCalendarAdapter,
    ReadOnlyDocumentAdapter,
)
from faroflow.integrations.google_calendar import (
    GOOGLE_CALENDAR_DELEGATED_SCOPE,
    GoogleCalendarAdapter,
    GoogleCalendarConfig,
    GoogleCalendarError,
)
from faroflow.integrations.google_drive import (
    GoogleDriveAdapter,
    GoogleDriveConfig,
    GoogleDriveError,
)
from faroflow.integrations.microsoft365 import (
    MICROSOFT_GRAPH_DELEGATED_PERMISSION,
    Microsoft365CalendarAdapter,
    Microsoft365CalendarConfig,
    Microsoft365CalendarError,
)
from faroflow.integrations.persistence import IntegrationStateError, IntegrationStateStore

__all__ = [
    "READ_ONLY_CAPABILITIES",
    "CalendarWindow",
    "ExternalCalendarEvent",
    "ExternalDocumentMetadata",
    "IntegrationCapabilities",
    "IntegrationContractError",
    "ReadOnlyCalendarAdapter",
    "ReadOnlyDocumentAdapter",
    "IntegrationStateError",
    "IntegrationStateStore",
    "MICROSOFT_GRAPH_DELEGATED_PERMISSION",
    "Microsoft365CalendarAdapter",
    "Microsoft365CalendarConfig",
    "Microsoft365CalendarError",
    "GOOGLE_CALENDAR_DELEGATED_SCOPE",
    "GoogleCalendarAdapter",
    "GoogleCalendarConfig",
    "GoogleCalendarError",
    "GoogleDriveAdapter",
    "GoogleDriveConfig",
    "GoogleDriveError",
]
