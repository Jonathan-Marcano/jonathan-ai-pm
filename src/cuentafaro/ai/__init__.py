"""Contrato neutral para proveedores de IA (Fase 3, CF3-01).

El dominio y los routers hablan con esta interfaz; cada proveedor (local por
reglas hoy, un SDK pagado mañana) implementa el mismo contrato detrás de un
adaptador. El dominio nunca importa SDKs externos.
"""

from __future__ import annotations

from cuentafaro.ai.base import (
    AiProvider,
    Anomaly,
    CategorySuggestion,
    CategorySuggestionContext,
    Insight,
    MonthFacts,
    SuggestionReason,
)
from cuentafaro.ai.rule_based import RuleBasedProvider
from cuentafaro.services import DomainRuleError

__all__ = [
    "AiProvider",
    "Anomaly",
    "CategorySuggestion",
    "CategorySuggestionContext",
    "Insight",
    "MonthFacts",
    "RuleBasedProvider",
    "SuggestionReason",
    "get_provider",
]

# Proveedores registrados: nombre canónico -> fábrica de adaptador.
_PROVIDERS: dict[str, type[AiProvider]] = {
    "rule_based": RuleBasedProvider,
}


def get_provider(name: str | None = None) -> AiProvider:
    """Devuelve el adaptador registrado para `name` (o el de configuración).

    `settings.llm_provider` vacío o "rule_based" selecciona el adaptador local
    gratuito. Cualquier otro nombre sin adaptador registrado es un error
    controlado del dominio (nunca se cae a un proveedor por defecto pagado).
    """
    from cuentafaro.config import get_settings

    settings = get_settings()
    provider_name = (name or settings.llm_provider or "").strip().lower()
    if not provider_name or provider_name in {"local", "rules", "rule_based"}:
        provider_name = "rule_based"
    factory = _PROVIDERS.get(provider_name)
    if factory is None:
        raise DomainRuleError(
            f"Proveedor de IA '{provider_name}' no está registrado; use 'rule_based'"
        )
    return factory()
