"""Centralized exception handlers for the FastAPI app.

Register these in app.py so all error responses are consistent.
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import Request
from fastapi.responses import JSONResponse

from awaithumans.server.services.task_service import (
    TaskAlreadyTerminalError,
    TaskNotFoundError,
)

logger = logging.getLogger("awaithumans.server.exceptions")


async def task_not_found_handler(request: Request, exc: TaskNotFoundError) -> JSONResponse:
    return JSONResponse(
        status_code=404,
        content={
            "error": "TASK_NOT_FOUND",
            "message": str(exc),
            "docs": "https://awaithumans.dev/docs/troubleshooting#task-not-found",
        },
    )


async def task_already_terminal_handler(
    request: Request, exc: TaskAlreadyTerminalError
) -> JSONResponse:
    return JSONResponse(
        status_code=409,
        content={
            "error": "TASK_ALREADY_TERMINAL",
            "message": str(exc),
            "docs": "https://awaithumans.dev/docs/troubleshooting#task-already-terminal",
        },
    )


async def generic_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.exception("Unhandled exception on %s %s", request.method, request.url.path)
    return JSONResponse(
        status_code=500,
        content={
            "error": "INTERNAL_ERROR",
            "message": "An unexpected error occurred.",
            "docs": "https://awaithumans.dev/docs/troubleshooting#internal-error",
        },
    )


exception_handlers: dict[type[Exception], Any] = {
    TaskNotFoundError: task_not_found_handler,
    TaskAlreadyTerminalError: task_already_terminal_handler,
    Exception: generic_exception_handler,
}
