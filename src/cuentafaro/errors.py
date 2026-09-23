from __future__ import annotations

import logging

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError

from cuentafaro.services import DomainRuleError

logger = logging.getLogger("cuentafaro")


def configure_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(KeyError)
    async def not_found(_request: Request, exc: KeyError) -> JSONResponse:
        return JSONResponse(status_code=404, content={"detail": f"Recurso no encontrado: {exc}"})

    @app.exception_handler(DomainRuleError)
    async def domain_rejection(_request: Request, exc: DomainRuleError) -> JSONResponse:
        return JSONResponse(status_code=422, content={"detail": str(exc)})

    @app.exception_handler(IntegrityError)
    async def conflict(_request: Request, exc: IntegrityError) -> JSONResponse:
        logger.warning("Conflicto de integridad: %s", exc.orig)
        return JSONResponse(status_code=409, content={"detail": "Conflicto con datos existentes"})
