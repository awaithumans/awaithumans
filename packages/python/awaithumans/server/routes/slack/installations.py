"""Slack installations CRUD — list + uninstall + workspace members.

Public shape never includes `bot_token` (encrypted, stays server-side).
Dashboard Settings page lists these and offers per-row uninstall.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Path
from fastapi.responses import Response
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from awaithumans.server.channels.slack.client import get_client_for_team
from awaithumans.server.db.connection import get_session
from awaithumans.server.schemas.slack import SlackInstallationResponse
from awaithumans.server.services.slack_installation_service import (
    delete_installation,
    list_installations,
)

router = APIRouter()
logger = logging.getLogger("awaithumans.server.routes.slack.installations")


class SlackMemberResponse(BaseModel):
    """A member of a Slack workspace — enough to render a picker.

    We deliberately don't forward the full Slack profile; dashboard
    only needs enough to label the row and record the stable ID."""

    id: str            # Slack user ID (U… / W…)
    name: str          # @handle ("alice")
    real_name: str | None
    display_name: str | None
    is_admin: bool


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


@router.get(
    "/installations/{team_id}/members",
    response_model=list[SlackMemberResponse],
)
async def list_workspace_members(
    team_id: str = Path(..., min_length=1, max_length=50),
    session: AsyncSession = Depends(get_session),
) -> list[SlackMemberResponse]:
    """List non-bot, active members of a Slack workspace.

    Powers the dashboard's "pick a Slack member" picker when adding a
    user to the directory. Calls Slack's `users.list` via the stored
    bot token — requires `users:read` scope on the installation.

    Returns 404 if we don't have an installation for the team. 502 if
    Slack rejects the API call (missing scope, token revoked) —
    operator needs to reinstall. Bots, deactivated accounts, and the
    Slackbot pseudo-user are filtered out so the picker only shows
    humans the operator can actually assign tasks to.
    """
    client = await get_client_for_team(session, team_id)
    if client is None:
        raise HTTPException(
            status_code=404,
            detail=(
                f"No Slack installation for team '{team_id}'. "
                "Install the awaithumans app to this workspace first."
            ),
        )

    try:
        resp = await client.users_list()
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "Slack users.list failed for team_id=%s: %s", team_id, exc
        )
        raise HTTPException(
            status_code=502,
            detail=(
                "Slack rejected users.list. The installation may be "
                "missing the 'users:read' scope, or the token was "
                "revoked. Reinstall the workspace from Settings → Slack."
            ),
        ) from exc

    out: list[SlackMemberResponse] = []
    for m in resp.data.get("members", []):  # type: ignore[attr-defined]
        if m.get("deleted") or m.get("is_bot") or m.get("id") == "USLACKBOT":
            continue
        profile = m.get("profile") or {}
        out.append(
            SlackMemberResponse(
                id=m["id"],
                name=m.get("name") or "",
                real_name=profile.get("real_name") or m.get("real_name"),
                display_name=profile.get("display_name") or None,
                is_admin=bool(m.get("is_admin") or m.get("is_owner")),
            )
        )

    # Stable sort — real_name, falling back to handle. Keeps the UI
    # order predictable across refetches.
    out.sort(key=lambda u: (u.real_name or u.name or u.id).lower())
    return out
