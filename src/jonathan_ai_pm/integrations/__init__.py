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
from jonathan_ai_pm.integrations.microsoft365 import (
    MICROSOFT_GRAPH_DELEGATED_PERMISSION,
    Microsoft365CalendarAdapter,
    Microsoft365CalendarConfig,
    Microsoft365CalendarError,
)
from jonathan_ai_pm.integrations.persistence import IntegrationStateError, IntegrationStateStore
from jonathan_ai_pm.integrations.reconciliation import (
    CalendarReconciler,
    CalendarReconciliationError,
    CalendarReconciliationResult,
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
    "IntegrationStateError",
    "IntegrationStateStore",
    "MICROSOFT_GRAPH_DELEGATED_PERMISSION",
    "Microsoft365CalendarAdapter",
    "Microsoft365CalendarConfig",
    "Microsoft365CalendarError",
    "CalendarReconciler",
    "CalendarReconciliationError",
    "CalendarReconciliationResult",
]
