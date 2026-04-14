"""Health check route."""

from __future__ import annotations

from fastapi import APIRouter

from awaithumans import __version__
from awaithumans.server.schemas import HealthResponse

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    return HealthResponse(status="ok", version=__version__)
