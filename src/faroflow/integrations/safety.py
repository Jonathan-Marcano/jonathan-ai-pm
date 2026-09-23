"""Startup and sync guards that keep provider access strictly read-only.

Phase 2 integrates providers through delegated read-only permissions only. These helpers
fail loudly when a provider registers by accident with write capability: either at startup
(``assert_registered_providers_read_only``) so the process refuses to boot, or per sync run
(``check_adapter_read_only``) so a misconfigured adapter is reported as a failed run instead
of mutating provider data.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from faroflow.integrations.contracts import (
    READ_ONLY_CAPABILITIES,
    IntegrationCapabilities,
)
from faroflow.integrations.google_calendar import GoogleCalendarAdapter
from faroflow.integrations.google_drive import GoogleDriveAdapter
from faroflow.integrations.microsoft365 import Microsoft365CalendarAdapter

_WRITE_SCOPE_MARKERS = (
    ".write",
    "readwrite",
    ".readwrite",
    "calendars.readwrite",
    "drive.file",
    "mail.send",
)


class ProviderSafetyError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class ProviderCheck:
    name: str
    source_system: str | None
    delegated_scope: str | None
    capabilities: IntegrationCapabilities


def check_adapter_read_only(
    *,
    name: str,
    source_system: str,
    delegated_scope: str | None,
    capabilities: IntegrationCapabilities,
) -> None:
    """Reject adapters that request write capabilities or write scopes."""
    if capabilities.create or capabilities.update or capabilities.delete:
        raise ProviderSafetyError(
            f"{name} ({source_system}) declares write capabilities; "
            "read-only integration requires create/update/delete all false"
        )
    if delegated_scope:
        check_scope_read_only(delegated_scope, name)
    if capabilities is not READ_ONLY_CAPABILITIES and not (
        capabilities.read
        and not (capabilities.create or capabilities.update or capabilities.delete)
    ):
        raise ProviderSafetyError(
            f"{name} ({source_system}) must advertise read capability"
        )


def check_scope_read_only(scope: str, provider_name: str) -> None:
    normalized = scope.strip().lower()
    if not normalized:
        raise ProviderSafetyError(f"{provider_name} declares an empty delegated scope")
    if any(marker in normalized for marker in _WRITE_SCOPE_MARKERS):
        raise ProviderSafetyError(
            f"{provider_name} declares a write scope '{scope}'; "
            "read-only integration requires a read-only delegated scope"
        )


def check_read_only_adapter(adapter: object) -> None:
    """Reject an adapter instance that requests write capability at sync time."""
    provider_type = type(adapter)
    check_adapter_read_only(
        name=provider_type.__name__,
        source_system=getattr(adapter, "source_system", None),
        delegated_scope=getattr(adapter, "delegated_scope", None)
        or getattr(adapter, "delegated_permission", None),
        capabilities=getattr(adapter, "capabilities", READ_ONLY_CAPABILITIES),
    )


def check_messaging_adapter(adapter: object) -> None:
    """Reject a messaging adapter that is unsafe for the inbound capture path.

    Inbound ingestion may only read a provider and feed the inbox; the adapter must advertise
    read capability and no wider FaroFlow write capability. Outbound confirmations are handled
    separately by ``OutboundPolicy`` and never bypass this guard.
    """
    provider_type = type(adapter)
    check_adapter_read_only(
        name=provider_type.__name__,
        source_system=getattr(adapter, "source_system", None),
        delegated_scope=getattr(adapter, "delegated_scope", None)
        or getattr(adapter, "delegated_permission", None),
        capabilities=getattr(adapter, "capabilities", READ_ONLY_CAPABILITIES),
    )
    if not callable(getattr(adapter, "list_messages", None)):
        raise ProviderSafetyError(
            f"{provider_type.__name__} does not implement the messaging inbound contract"
        )


_REGISTERED_PROVIDERS: Sequence[type] = (
    Microsoft365CalendarAdapter,
    GoogleCalendarAdapter,
    GoogleDriveAdapter,
)


def _provider_checks() -> list[ProviderCheck]:
    return [
        ProviderCheck(
            name=provider.__name__,
            source_system=getattr(provider, "source_system", None),
            delegated_scope=getattr(provider, "delegated_scope", None)
            or getattr(provider, "delegated_permission", None),
            capabilities=getattr(provider, "capabilities", READ_ONLY_CAPABILITIES),
        )
        for provider in _REGISTERED_PROVIDERS
    ]


def assert_registered_providers_read_only() -> list[ProviderCheck]:
    """Run compile-time checks on every registered provider adapter.

    Called on application startup so a provider configured with write access prevents the
    process from booting instead of silently risking outbound mutations.
    """
    checks = _provider_checks()
    for check in checks:
        if check.source_system is not None:
            check_adapter_read_only(
                name=check.name,
                source_system=check.source_system,
                delegated_scope=check.delegated_scope,
                capabilities=check.capabilities,
            )
    return checks