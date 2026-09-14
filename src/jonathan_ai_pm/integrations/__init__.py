"""Provider-neutral Phase 2 integration contracts."""

from jonathan_ai_pm.integrations.contracts import (
    READ_ONLY_CAPABILITIES,
    CalendarWindow,
    ExternalCalendarEvent,
    ExternalDocumentMetadata,
    IntegrationCapabilities,
    IntegrationContractError,
    ReadOnlyCalendarAdapter,
    ReadOnlyDocumentAdapter,
)

__all__ = [
    "READ_ONLY_CAPABILITIES",
    "CalendarWindow",
    "ExternalCalendarEvent",
    "ExternalDocumentMetadata",
    "IntegrationCapabilities",
    "IntegrationContractError",
    "ReadOnlyCalendarAdapter",
    "ReadOnlyDocumentAdapter",
]
