"""Structured JSON logging for the awaithumans server.

Provides:
- JSON-formatted log output (one JSON object per line)
- Request ID correlation via contextvars
- Configurable log level via AWAITHUMANS_LOG_LEVEL env var

Usage:
    from awaithumans.server.core.logging_config import setup_logging, request_id_var

    # At app startup:
    setup_logging()

    # In middleware:
    request_id_var.set("some-uuid")
"""

from __future__ import annotations

import logging
import sys
from contextvars import ContextVar
from datetime import datetime, timezone

from awaithumans.utils.constants import SERVICE_NAME

request_id_var: ContextVar[str] = ContextVar("request_id", default="")


class AwaitHumansFormatter(logging.Formatter):
    """JSON-like structured formatter with request ID correlation."""

    def format(self, record: logging.LogRecord) -> str:
        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")
        level = record.levelname
        logger_name = record.name
        message = record.getMessage()

        req_id = request_id_var.get("")
        req_id_part = f' request_id={req_id}' if req_id else ""

        return f"{timestamp} [{level}] {logger_name}{req_id_part} — {message}"


def setup_logging(log_level: str = "INFO") -> None:
    """Configure structured logging for the application.

    Call this once at startup before any logging happens.
    """
    formatter = AwaitHumansFormatter()

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    root_logger.addHandler(handler)
    root_logger.setLevel(getattr(logging, log_level.upper(), logging.INFO))

    # Suppress noisy loggers
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)

    logging.getLogger("awaithumans.server").info("Logging configured (level=%s)", log_level)
