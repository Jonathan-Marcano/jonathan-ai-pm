"""Provider-neutral integration contracts (Phase 2 read-only providers, Phase 4 messaging)."""

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
from faroflow.integrations.messaging import (
    MAX_MESSAGE_CHARS,
    MAX_MESSAGES_PER_LISTING,
    ExternalInboundMessage,
    ExternalMessageReceipt,
    MessagingAdapter,
    OutboundConfirmationError,
    OutboundNotice,
    OutboundPolicy,
    outbound_preview_digest,
)
from faroflow.integrations.microsoft365 import (
    MICROSOFT_GRAPH_DELEGATED_PERMISSION,
    Microsoft365CalendarAdapter,
    Microsoft365CalendarConfig,
    Microsoft365CalendarError,
)
from faroflow.integrations.persistence import IntegrationStateError, IntegrationStateStore
from faroflow.integrations.telegram_messaging import (
    TelegramMessagingAdapter,
    TelegramMessagingConfig,
    TelegramMessagingError,
    TelegramMessagingNotConfigured,
    build_telegram_messaging_adapter,
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
    "GOOGLE_CALENDAR_DELEGATED_SCOPE",
    "GoogleCalendarAdapter",
    "GoogleCalendarConfig",
    "GoogleCalendarError",
    "GoogleDriveAdapter",
    "GoogleDriveConfig",
    "GoogleDriveError",
    "MAX_MESSAGE_CHARS",
    "MAX_MESSAGES_PER_LISTING",
    "ExternalInboundMessage",
    "ExternalMessageReceipt",
    "MessagingAdapter",
    "OutboundConfirmationError",
    "OutboundNotice",
    "OutboundPolicy",
    "outbound_preview_digest",
    "TelegramMessagingAdapter",
    "TelegramMessagingConfig",
    "TelegramMessagingError",
    "TelegramMessagingNotConfigured",
    "build_telegram_messaging_adapter",
]
