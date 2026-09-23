"""Contrato neutral de IA: tipos de dominio y protocolo `AiProvider` (CF3-01).

Los métodos reciben *hechos* del dominio (datos), nunca sesiones ni entidades.
Un proveedor LLM externo consumiría exactamente los mismos hechos, por lo que
cambiar de adaptador no toca el dominio.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable


@dataclass(frozen=True)
class SuggestionReason:
    label: str
    detail: str


@dataclass(frozen=True)
class CategorySuggestion:
    category_id: str
    category_name: str
    reason: str
    rank: int = 1
    confidence: float = 0.0


@dataclass(frozen=True)
class Insight:
    severity: str
    title: str
    detail: str
    category_id: str | None = None


@dataclass(frozen=True)
class Anomaly:
    category_id: str | None
    title: str
    detail: str
    severity: str = "warning"
    budget_id: str | None = None
    suggested_planned_amount: int | None = None


@dataclass(frozen=True)
class MonthFacts:
    household_id: str
    year: int
    month: int
    period: str
    income: int = 0
    expenses: int = 0
    budget_rows: list[dict] = field(default_factory=list)
    history: dict[str, dict] = field(default_factory=dict)


@dataclass(frozen=True)
class CategorySuggestionContext:
    household_id: str
    description: str
    kind: str = "expense"
    amount: int | None = None
    rules: list[dict] = field(default_factory=list)
    categories: list[dict] = field(default_factory=list)
    history: list[dict] = field(default_factory=list)


@runtime_checkable
class AiProvider(Protocol):
    """Contrato neutral. El dominio invoca estos métodos; el adaptador decide."""

    name: str

    def suggest_category(self, context: CategorySuggestionContext) -> list[CategorySuggestion]:
        """Sugiere categorías para un movimiento nuevo (nunca lo crea)."""
        ...

    def explain_month(self, facts: MonthFacts) -> list[Insight]:
        """Explica el mes (variaciones y resumen) usando solo hechos locales."""
        ...

    def detect_anomalies(self, facts: MonthFacts) -> list[Anomaly]:
        """Detecta gastos atípicos y propone ajustes; no aplica nada."""
        ...
