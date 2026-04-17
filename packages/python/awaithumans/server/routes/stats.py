"""Stats route — GET /api/stats/tasks?window_days=N.

Aggregate task metrics for the dashboard Analytics page. Gated by the
dashboard auth middleware like every other authenticated API.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from awaithumans.server.db.connection import get_session
from awaithumans.server.schemas.stats import TaskStats
from awaithumans.server.services.stats_service import get_task_stats

router = APIRouter(prefix="/stats", tags=["stats"])

# Bounds on window_days: at least 1 day of data, at most a year. Larger
# windows pull more rows into memory — see services/stats_service.py
# for why this is OK at MVP scale.
_MIN_WINDOW_DAYS = 1
_MAX_WINDOW_DAYS = 365


@router.get("/tasks", response_model=TaskStats)
async def task_stats(
    window_days: int = Query(
        default=30,
        ge=_MIN_WINDOW_DAYS,
        le=_MAX_WINDOW_DAYS,
        description="Lookback window for by-day / by-channel aggregates.",
    ),
    session: AsyncSession = Depends(get_session),
) -> TaskStats:
    return await get_task_stats(session, window_days=window_days)
