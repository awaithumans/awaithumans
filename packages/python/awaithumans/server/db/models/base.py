"""Shared utilities for database models."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4


def utc_now() -> datetime:
    """Current UTC timestamp for default field values."""
    return datetime.now(timezone.utc)


def new_id() -> str:
    """Generate a new hex UUID for primary keys."""
    return uuid4().hex
