"""Avisos programados del dominio (Fase 4, CF4-06/CF4-07).

Las plantillas y las reglas de programación viven en el dominio y la entrega se
hace por un proveedor neutral (``cuentafaro.messaging``). En este tramo el
proveedor es simulado: nada sale a una red real.
"""

from cuentafaro.notifications.scheduler import run_household_notifications
from cuentafaro.notifications.templates import (
    render_budget_deviation,
    render_monthly_close,
    render_upcoming_payment,
    render_weekly_summary,
)

__all__ = [
    "render_budget_deviation",
    "render_monthly_close",
    "render_upcoming_payment",
    "render_weekly_summary",
    "run_household_notifications",
]
