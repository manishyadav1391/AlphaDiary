"""FastAPI application factory.

Routers stay thin; business logic belongs in `app/services/`.

`require_session` is registered as an application-wide dependency rather than
on each router, so a new route is protected by default and opening one has to
be a deliberate edit to the allowlist in `app/deps.py` (FR-AUTH-05).
"""

from __future__ import annotations

import logging

from fastapi import Depends, FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.config import get_settings
from app.deps import API_PREFIX, require_session
from app.errors import ApiError, error_body
from app.logging_config import configure_logging
from app.routers import (
    auth,
    dashboard,
    health,
    importer,
    kite,
    playbook,
    sync,
    trades,
)

logger = logging.getLogger("tj.api")


def create_app() -> FastAPI:
    configure_logging()
    settings = get_settings()

    app = FastAPI(
        title="TJ API",
        version="0.2.0",
        docs_url=None if settings.is_production else "/docs",
        redoc_url=None,
        openapi_url=None if settings.is_production else "/openapi.json",
        dependencies=[Depends(require_session)],
    )

    for router in (
        health.router,
        auth.router,
        kite.router,
        sync.router,
        importer.router,
        trades.router,
        dashboard.router,
        playbook.router,
    ):
        app.include_router(router, prefix=API_PREFIX)

    @app.exception_handler(ApiError)
    async def api_error_handler(_: Request, exc: ApiError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content=error_body(exc.code, exc.message, exc.details),
        )

    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(_: Request, exc: StarletteHTTPException) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content=error_body("http_error", str(exc.detail)),
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(_: Request, exc: RequestValidationError) -> JSONResponse:
        return JSONResponse(
            status_code=422,
            content=error_body("validation_error", "Request validation failed"),
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        # Log the type and the path, never the exception text: it can carry a
        # connection string, a token or a broker payload.
        logger.exception(
            "Unhandled error", extra={"event": "unhandled_error", "path": request.url.path}
        )
        return JSONResponse(
            status_code=500,
            content=error_body("internal_error", "Something went wrong"),
        )

    return app


app = create_app()
