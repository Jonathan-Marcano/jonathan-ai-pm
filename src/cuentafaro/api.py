from __future__ import annotations

from fastapi import APIRouter, FastAPI

from cuentafaro.config import get_settings
from cuentafaro.errors import configure_exception_handlers
from cuentafaro.routers import (
    accounts,
    ai,
    audit,
    budgets,
    categories,
    dashboard,
    debts,
    goals,
    households,
    imports,
    messaging,
    notifications,
    projections,
    transactions,
    web,
)
from cuentafaro.security import install_log_redaction

# Los routers de finanzas se declaran sin prefijo propio para poder alojarlos
# bajo /api/v1 en la app standalone y bajo /api/v1/finance en Faro Flow.
API_ROUTERS = (
    households.router,
    accounts.router,
    categories.router,
    transactions.router,
    debts.router,
    goals.router,
    budgets.router,
    dashboard.router,
    projections.router,
    imports.router,
    ai.router,
    messaging.router,
    notifications.router,
    audit.router,
)


def create_app() -> FastAPI:
    install_log_redaction()
    settings = get_settings()
    app = FastAPI(title="CuentaFaro", version="0.1.0")
    configure_exception_handlers(app)
    api_v1 = APIRouter(prefix="/api/v1")
    for router in API_ROUTERS:
        api_v1.include_router(router)
    app.include_router(api_v1)
    app.include_router(web.router)

    @app.get("/health")
    def health() -> dict:
        return {
            "status": "ok",
            "app_env": settings.app_env,
            "timezone": settings.app_timezone,
            "base_currency": settings.base_currency,
        }

    return app


app = create_app()
