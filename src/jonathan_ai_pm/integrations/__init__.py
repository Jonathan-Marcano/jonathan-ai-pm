"""Provider-neutral Phase 2 integration contracts."""

from jonathan_ai_pm.integrations.associations import (
    CalendarAssociationError,
    CalendarAssociationService,
)
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
from jonathan_ai_pm.integrations.maintenance import (
    DisconnectionResult,
    IntegrationMaintenanceError,
    IntegrationMaintenanceService,
    RetentionResult,
)
from jonathan_ai_pm.integrations.microsoft365 import (
    MICROSOFT_GRAPH_DELEGATED_PERMISSION,
    Microsoft365CalendarAdapter,
    Microsoft365CalendarConfig,
    Microsoft365CalendarError,
)
from jonathan_ai_pm.integrations.operations import (
    CalendarAdapterBinding,
    CalendarAdapterRegistry,
    CalendarOperationError,
    CalendarSyncCoordinator,
)
from jonathan_ai_pm.integrations.persistence import IntegrationStateError, IntegrationStateStore
from jonathan_ai_pm.integrations.reconciliation import (
    CalendarReconciler,
    CalendarReconciliationError,
    CalendarReconciliationResult,
)
from jonathan_ai_pm.integrations.security import (
    MICROSOFT_GRAPH_READ_ONLY_PERMISSIONS,
    IntegrationSecurityError,
    normalize_permissions,
    require_read_only_capabilities,
    validate_microsoft_graph_permissions,
)

__all__ = [
    "CalendarAssociationError",
    "CalendarAssociationService",
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
    "IntegrationMaintenanceError",
    "IntegrationMaintenanceService",
    "RetentionResult",
    "DisconnectionResult",
    "IntegrationSecurityError",
    "MICROSOFT_GRAPH_READ_ONLY_PERMISSIONS",
    "normalize_permissions",
    "require_read_only_capabilities",
    "validate_microsoft_graph_permissions",
    "MICROSOFT_GRAPH_DELEGATED_PERMISSION",
    "Microsoft365CalendarAdapter",
    "Microsoft365CalendarConfig",
    "Microsoft365CalendarError",
    "CalendarAdapterBinding",
    "CalendarAdapterRegistry",
    "CalendarOperationError",
    "CalendarSyncCoordinator",
    "CalendarReconciler",
    "CalendarReconciliationError",
    "CalendarReconciliationResult",
]
