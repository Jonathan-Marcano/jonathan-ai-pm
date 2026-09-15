from __future__ import annotations

from collections.abc import Iterable

from jonathan_ai_pm.integrations.contracts import IntegrationCapabilities

MICROSOFT_GRAPH_READ_ONLY_PERMISSIONS = frozenset(
    {
        "calendars.readbasic",
        "openid",
        "profile",
        "offline_access",
    }
)
MICROSOFT_GRAPH_REQUIRED_PERMISSION = "calendars.readbasic"


class IntegrationSecurityError(ValueError):
    pass


def normalize_permissions(permissions: str | Iterable[str]) -> tuple[str, ...]:
    values = permissions.replace(",", " ").split() if isinstance(permissions, str) else permissions
    normalized = tuple(permission.strip().lower() for permission in values if permission.strip())
    if len(normalized) != len(set(normalized)):
        raise IntegrationSecurityError("Integration permissions cannot contain duplicates")
    return normalized


def validate_microsoft_graph_permissions(
    permissions: str | Iterable[str],
    *,
    require_calendar_read: bool = True,
) -> tuple[str, ...]:
    normalized = normalize_permissions(permissions)
    unsupported = sorted(set(normalized) - MICROSOFT_GRAPH_READ_ONLY_PERMISSIONS)
    if unsupported:
        raise IntegrationSecurityError(
            "Microsoft Graph permission is not approved for read-only use: "
            + ", ".join(unsupported)
        )
    if require_calendar_read and MICROSOFT_GRAPH_REQUIRED_PERMISSION not in normalized:
        raise IntegrationSecurityError("Microsoft Graph requires Calendars.ReadBasic")
    return normalized


def require_read_only_capabilities(capabilities: IntegrationCapabilities) -> None:
    if not isinstance(capabilities, IntegrationCapabilities):
        raise IntegrationSecurityError("Integration capabilities must be declared")
    if not capabilities.read:
        raise IntegrationSecurityError("Integration must declare read capability")
    if capabilities.create or capabilities.update or capabilities.delete:
        raise IntegrationSecurityError("Integration write capabilities are not allowed")
