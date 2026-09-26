import logging
import time
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from faroflow import __version__
from faroflow.integrations.safety import assert_registered_providers_read_only
from faroflow.security import install_log_redaction, redact_text

from .routes_captures import router as captures_router
from .routes_catalog import router as catalog_router
from .routes_integrations import router as integrations_router
from .routes_meetings import router as meetings_router
from .routes_system import router as system_router
from .routes_translations import router as translations_router
from .routes_unified import router as unified_router
from .routes_web import router as web_router
from .routes_work import router as work_router

logger = logging.getLogger("faroflow.api")

STATIC_DIR = Path(__file__).resolve().parents[3] / "static"


@asynccontextmanager
async def lifespan(_app: FastAPI):
    install_log_redaction()
    assert_registered_providers_read_only()
    yield


app = FastAPI(title="FaroFlow", version=__version__, lifespan=lifespan)


@app.middleware("http")
async def log_requests(request: Request, call_next):
    started = time.perf_counter()
    response = await call_next(request)
    duration_ms = (time.perf_counter() - started) * 1000
    # El JS del cliente se revalida siempre. StaticFiles no envía Cache-Control,
    # así que Chrome aplica su heurístico de frescura (10% de la antigüedad del
    # Last-Modified) y puede servir un módulo viejo sin preguntar al servidor:
    # el arreglo llegaba al disco pero no al navegador y el síntoma era "hay que
    # recargar con F5 para que aparezca el cambio".
    if request.url.path.startswith("/static"):
        response.headers["Cache-Control"] = "no-cache"
    logger.info(
        "request method=%s url=%s status=%s duration_ms=%.1f",
        request.method,
        redact_text(str(request.url)),
        response.status_code,
        duration_ms,
    )
    return response


for router in (
    system_router,
    catalog_router,
    work_router,
    meetings_router,
    captures_router,
    translations_router,
    unified_router,
    integrations_router,
    web_router,
):
    app.include_router(router)


# Área Finanzas: routers de CuentaFaro alojados bajo /api/v1/finance.
# Conservan sus propias dependencies (session de finanzas) y excepciones.
try:
    from fastapi import APIRouter

    from cuentafaro.api import API_ROUTERS
    from cuentafaro.errors import configure_exception_handlers as _configure_finance_handlers

    finance_router = APIRouter(prefix="/api/v1/finance")
    for _router in API_ROUTERS:
        finance_router.include_router(_router)
    app.include_router(finance_router)
    _configure_finance_handlers(app)
except Exception as exc:  # pragma: no cover - arranque defensivo
    logger.error("no se pudo montar el área Finanzas: %s", redact_text(str(exc)))


app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/favicon.ico", include_in_schema=False)
def favicon():
    return FileResponse(STATIC_DIR / "favicon.ico", media_type="image/x-icon")


@app.get("/manifest.webmanifest", include_in_schema=False)
def web_manifest():
    return FileResponse(
        STATIC_DIR / "manifest.webmanifest", media_type="application/manifest+json"
    )