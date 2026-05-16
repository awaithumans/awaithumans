"""Version API response schema."""

from __future__ import annotations

from pydantic import BaseModel


class VersionResponse(BaseModel):
    """Server-version payload returned by `GET /api/version`.

    `name` lets clients confirm they're talking to an awaithumans
    server (vs e.g. a misconfigured reverse proxy pointing at the
    wrong upstream). `version` is the package version — useful for
    SDK compatibility checks before authenticating.
    """

    name: str = "awaithumans"
    version: str
