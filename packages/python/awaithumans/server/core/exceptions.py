"""Centralized exception handler for the FastAPI app.

One handler for all ServiceError subclasses — no per-exception functions.
The ServiceError base class carries status_code, error_code, and docs_url,
so the handler just reads them off the exception.
"""

from __future__ import annotations

import logging

from fastapi import Request

from awaithumans.utils.constants import DOCS_TROUBLESHOOTING_URL
from fastapi.responses import JSONResponse

from awaithumans.server.services.exceptions import ServiceError

logger = logging.getLogger("awaithumans.server.exceptions")


async def service_error_handler(request: Request, exc: ServiceError) -> JSONResponse:
    """Handle all ServiceError subclasses with a single function.

    Reads status_code, error_code, message, and docs_url from the exception.
    No need to register a separate handler for each exception type.
    """
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": exc.error_code,
            "message": exc.message,
            "docs": exc.docs_url,
        },
    )


async def generic_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Catch-all for unhandled exceptions. Logs the full traceback."""
    logger.exception("Unhandled exception on %s %s", request.method, request.url.path)
    return JSONResponse(
        status_code=500,
        content={
            "error": "INTERNAL_ERROR",
            "message": "An unexpected error occurred.",
            "docs": f"{DOCS_TROUBLESHOOTING_URL}#internal-error",
        },
    )


exception_handlers: dict[type[Exception], object] = {
    ServiceError: service_error_handler,
    Exception: generic_exception_handler,
}
