"""Plantillas de notificación del dominio (Fase 4, CF4-06).

Cada plantilla produce título y cuerpo con los valores ya resueltos: así el
registro auditable conserva exactamente lo que se envió. Son deterministas:
mismo insumo → mismo aviso.

Kinds estables (viven en el dominio, independientes del proveedor):
``upcoming_payment``, ``weekly_summary``, ``budget_deviation`` y
``monthly_close``.
"""

from __future__ import annotations

from datetime import date


def _money(value: int) -> str:
    return f"${value:,}".replace(",", ".")


def _pct(planned: int, actual: int) -> str:
    if planned <= 0:
        return "—"
    return f"{round((actual - planned) / planned * 100)}%"


def render_upcoming_payment(
    *, debt_name: str, amount: int, due_date: date, days_left: int
) -> tuple[str, str]:
    """Aviso de pago próximo por vencer (recupera CF1-26: deudas/cuotas)."""
    when = "hoy" if days_left <= 0 else f"en {days_left} día{'s' if days_left != 1 else ''}"
    title = "Pago próximo por vencer"
    body = f"{debt_name} vence el {due_date.isoformat()} ({when}): {_money(amount)}."
    return title, body


def render_weekly_summary(
    *, week_start: date, week_end: date, income: int, expenses: int, balance: int
) -> tuple[str, str]:
    """Resumen semanal de ingresos, gastos y balance del período."""
    title = "Resumen semanal de CuentaFaro"
    body = "\n".join(
        [
            f"Resumen {week_start.isoformat()} → {week_end.isoformat()}",
            f"Ingresos: {_money(income)}",
            f"Gastos: {_money(expenses)}",
            f"Balance: {_money(balance)}",
        ]
    )
    return title, body


def render_budget_deviation(rows: list[dict]) -> tuple[str, str]:
    """Aviso de desviación vs presupuesto (recupera CF1-27 en dashboard).

    ``rows``: dicts con ``category_name``, ``planned`` y ``actual``; sólo las
    categorías que ya superaron lo planificado.
    """
    lines = []
    for row in rows[:5]:
        lines.append(
            f"• {row['category_name']}: {_money(row['actual'])} vs "
            f"{_money(row['planned'])} planificado ({_pct(row['planned'], row['actual'])} arriba)"
        )
    title = "Desviación frente al presupuesto"
    body = "Categorías sobre planificado:\n" + "\n".join(lines)
    return title, body


def render_monthly_close(
    *, period: str, expenses: int, budget_total: int | None
) -> tuple[str, str]:
    """Solicitud de cierre de mes: invita a cerrar el período y revisar el gasto."""
    title = "Solicitud de cierre de mes"
    body_lines = [f"Cierre el período {period} para dejar el mes listo."]
    body_lines.append(f"Gastos del mes: {_money(expenses)}")
    if budget_total is not None:
        body_lines.append(f"Presupuesto del mes: {_money(budget_total)}")
    return title, "\n".join(body_lines)
