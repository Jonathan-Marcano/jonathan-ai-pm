"""Registro de proveedores de mensajería (Fase 4, CF4-01).

`get_messaging_provider()` devuelve el adaptador activo según
`settings.messaging_provider`: vacío o "simulated" usa el canal simulado local.
Un nombre sin adaptador registrado es un error controlado del dominio.
"""

from __future__ import annotations

from cuentafaro.messaging.base import MessagingProvider, OutboundMessage, SendReceipt
from cuentafaro.messaging.simulated import SimulatedProvider
from cuentafaro.services import DomainRuleError

__all__ = [
    "MessagingProvider",
    "OutboundMessage",
    "SendReceipt",
    "SimulatedProvider",
    "get_messaging_provider",
]

_PROVIDERS: dict[str, type[MessagingProvider]] = {
    "simulated": SimulatedProvider,
}


def get_messaging_provider(name: str | None = None) -> MessagingProvider:
    """Devuelve el adaptador de mensajería registrado para `name`."""
    from cuentafaro.config import get_settings

    settings = get_settings()
    provider_name = (name or settings.messaging_provider or "").strip().lower()
    if not provider_name or provider_name in {"local", "simulated", "mock"}:
        provider_name = "simulated"
    factory = _PROVIDERS.get(provider_name)
    if factory is None:
        raise DomainRuleError(
            f"Proveedor de mensajería '{provider_name}' no está registrado; use 'simulated'"
        )
    return factory()
