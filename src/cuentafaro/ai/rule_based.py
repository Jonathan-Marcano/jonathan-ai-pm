"""Adaptador local gratuito: clasificación por reglas y heurísticas (CF3-02).

No envía nada a ningún proveedor externo. Reutiliza la semántica de las reglas
de `import_category_rules` (CF2-12) para clasificar descripciones y produce:
- sugerencia de categoría (reglas primero, después memoria de descripciones),
- explicación de variaciones del mes,
- detección de anomalías y propuestas de ajuste (nunca se aplican solas).
"""

from __future__ import annotations

from cuentafaro.ai.base import (
    Anomaly,
    CategorySuggestion,
    CategorySuggestionContext,
    Insight,
    MonthFacts,
)

MIN_ABS = 10_000
ANOMALY_FACTOR = 1.5
ANOMALY_MIN_DELTA = 40_000


def _format_clp(amount: int) -> str:
    return f"{amount:,}".replace(",", ".")


class RuleBasedProvider:
    name = "rule_based"

    def suggest_category(self, context: CategorySuggestionContext) -> list[CategorySuggestion]:
        by_id = {category["id"]: category for category in context.categories}
        haystack = (context.description or "").strip().lower()
        if not haystack:
            return []

        suggestions: list[CategorySuggestion] = []
        seen: set[str] = set()
        for rule in context.rules:
            if not rule.get("enabled", True):
                continue
            pattern = (rule.get("pattern") or "").strip().lower()
            category_id = rule.get("category_id")
            if not pattern or not category_id or category_id in seen:
                continue
            if pattern in haystack:
                category = by_id.get(category_id)
                if category is None:
                    continue
                if context.kind and category.get("kind") != context.kind:
                    continue
                suggestions.append(
                    CategorySuggestion(
                        category_id=category_id,
                        category_name=category["name"],
                        reason=f"coincide con la regla «{pattern}»",
                        rank=len(suggestions) + 1,
                        confidence=1.0,
                    )
                )
                seen.add(category_id)
        if suggestions:
            return suggestions

        best: dict | None = None
        for entry in context.history:
            description = (entry.get("description") or "").strip().lower()
            if not description:
                continue
            if description in haystack or haystack in description:
                if best is None or (entry.get("count") or 0) > (best.get("count") or 0):
                    best = entry
        if best and best.get("category_id"):
            category = by_id.get(best["category_id"])
            if category and (not context.kind or category.get("kind") == context.kind):
                suggestions.append(
                    CategorySuggestion(
                        category_id=category["id"],
                        category_name=category["name"],
                        reason="se usó antes para descripciones similares",
                        rank=1,
                        confidence=0.6,
                    )
                )
        return suggestions

    def explain_month(self, facts: MonthFacts) -> list[Insight]:
        insights: list[Insight] = []
        if facts.income > 0 and facts.expenses > facts.income:
            insights.append(
                Insight(
                    severity="danger",
                    title="Se gastó más de lo que entró",
                    detail=(
                        f"Los gastos del mes ({_format_clp(facts.expenses)}) superan los "
                        f"ingresos ({_format_clp(facts.income)}). Conviene revisar el presupuesto."
                    ),
                )
            )
        elif facts.expenses > 0:
            saved = facts.income - facts.expenses
            insights.append(
                Insight(
                    severity="info",
                    title="Balance del mes positivo",
                    detail=(
                        f"Ingresos {_format_clp(facts.income)} menos gastos "
                        f"{_format_clp(facts.expenses)} dejan "
                        f"{_format_clp(max(saved, 0))} disponibles."
                    ),
                )
            )
        for row in facts.budget_rows:
            planned = row.get("planned_amount") or 0
            actual = row.get("actual_amount") or 0
            if planned > 0 and actual > planned:
                over = actual - planned
                percent = round(over / planned * 100)
                insights.append(
                    Insight(
                        severity="warning",
                        title=f"«{row.get('name')}» excedió su presupuesto",
                        detail=(
                            f"Se gastaron {_format_clp(actual)} contra {_format_clp(planned)} "
                            f"planificados ({percent}% sobre)."
                        ),
                        category_id=row.get("category_id"),
                    )
                )
        if facts.budget_rows:
            top = max(
                facts.budget_rows,
                key=lambda row: row.get("actual_amount") or 0,
                default=None,
            )
            if top and (top.get("actual_amount") or 0) > 0:
                insights.append(
                    Insight(
                        severity="info",
                        title="Mayor partida del mes",
                        detail=(
                            f"«{top.get('name')}» concentró "
                            f"{_format_clp(top.get('actual_amount') or 0)} del gasto del mes."
                        ),
                        category_id=top.get("category_id"),
                    )
                )
        return insights[:6]

    def detect_anomalies(self, facts: MonthFacts) -> list[Anomaly]:
        anomalies: list[Anomaly] = []
        history = facts.history or {}
        for category_id, info in history.items():
            average = info.get("avg") or 0
            current = info.get("current") or 0
            if average < MIN_ABS or current < average * ANOMALY_FACTOR:
                continue
            delta = current - average
            if delta < ANOMALY_MIN_DELTA:
                continue
            factor = round(current / average, 1)
            suggested = _next_planned(average)
            anomalies.append(
                Anomaly(
                    category_id=category_id,
                    title=f"Gasto atípico en {info.get('name') or 'una categoría'}",
                    detail=(
                        f"Este mes gastó {_format_clp(current)} vs el promedio de "
                        f"{_format_clp(int(average))} de meses anteriores ({factor}x)."
                    ),
                    severity="warning",
                    budget_id=info.get("budget_id"),
                    suggested_planned_amount=suggested,
                )
            )
        return sorted(anomalies, key=lambda a: a.suggested_planned_amount or 0, reverse=True)


def _next_planned(average: int) -> int:
    return int(round(average * 1.2, 0)) if average > 0 else 0
