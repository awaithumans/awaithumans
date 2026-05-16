"""Version endpoint — exposes the server's running package version.

Public route. Useful for:
  - Ops / monitoring: confirm the deployed version after a rollout.
  - SDK compatibility checks: an SDK can probe the server's version
    before authenticating, e.g. to surface "this SDK is older than
    the server" hints.
  - Misconfig debugging: confirm a reverse proxy points at the right
    upstream (the `name` field disambiguates from a 404'd default
    upstream that happens to return JSON).

`/api/health` already includes `version`, but mixing concerns means
ops tooling probing readiness needs to know about an unrelated payload
field. A dedicated `/api/version` keeps the two contracts separate.
"""

from __future__ import annotations

from fastapi import APIRouter

from awaithumans import __version__
from awaithumans.server.schemas import VersionResponse

router = APIRouter(tags=["version"])


@router.get("/version", response_model=VersionResponse)
async def version_check() -> VersionResponse:
    return VersionResponse(name="awaithumans", version=__version__)
