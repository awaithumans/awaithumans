"""Health check route."""

from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

from awaithumans import __version__

router = APIRouter(tags=["health"])


class HealthResponse(BaseModel):
    status: str = "ok"
    version: str


@router.get("/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    return HealthResponse(status="ok", version=__version__)
