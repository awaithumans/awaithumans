"""Slack installations CRUD — list + uninstall.

Public shape never includes `bot_token` (encrypted, stays server-side).
Dashboard Settings page lists these and offers per-row uninstall.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Path
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from awaithumans.server.db.connection import get_session
from awaithumans.server.schemas.slack import SlackInstallationResponse
from awaithumans.server.services.slack_installation_service import (
    delete_installation,
    list_installations,
)

router = APIRouter()
logger = logging.getLogger("awaithumans.server.routes.slack.installations")


def _to_public(row) -> SlackInstallationResponse:
    return SlackInstallationResponse(
        team_id=row.team_id,
        team_name=row.team_name,
        bot_user_id=row.bot_user_id,
        scopes=row.scopes,
        enterprise_id=row.enterprise_id,
        installed_by_user_id=row.installed_by_user_id,
        installed_at=row.installed_at.isoformat(),
        updated_at=row.updated_at.isoformat(),
    )


@router.get("/installations", response_model=list[SlackInstallationResponse])
async def list_slack_installations(
    session: AsyncSession = Depends(get_session),
) -> list[SlackInstallationResponse]:
    rows = await list_installations(session)
    return [_to_public(r) for r in rows]


@router.delete(
    "/installations/{team_id}",
    status_code=204,
    # Override the default JSONResponse — 204 forbids a response body, and
    # FastAPI's default response would try to emit one.
    response_class=Response,
)
async def uninstall_slack_workspace(
    team_id: str = Path(..., min_length=1, max_length=50),
    session: AsyncSession = Depends(get_session),
) -> Response:
    ok = await delete_installation(session, team_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Installation not found.")
    logger.info("Uninstalled Slack workspace team_id=%s", team_id)
    return Response(status_code=204)
