"""Server middleware — request ID tracking, error handling."""

from __future__ import annotations

import logging
import uuid

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

from awaithumans.server.core.logging_config import request_id_var

logger = logging.getLogger("awaithumans.server.middleware")


class RequestIDMiddleware(BaseHTTPMiddleware):
    """Assign a unique request ID to every incoming request.

    The ID is stored in a contextvar so all logs within the request include it,
    and it is returned in the X-Request-ID response header for correlation.
    """

    async def dispatch(self, request: Request, call_next) -> Response:
        req_id = request.headers.get("X-Request-ID", uuid.uuid4().hex[:16])
        request_id_var.set(req_id)
        response: Response = await call_next(request)
        response.headers["X-Request-ID"] = req_id
        return response
