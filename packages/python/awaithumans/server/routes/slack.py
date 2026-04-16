"""Slack interactivity webhook + OAuth install flow.

Interactivity (`POST /interactions`):
  Slack POSTs here for every button click and modal submission. The body
  is `application/x-www-form-urlencoded` with a single `payload` field
  whose value is a JSON string. Two payload shapes are handled:

  - `block_actions`: user clicked the "Open in Slack" button on the
    initial message → open a modal via `views.open`.
  - `view_submission`: user submitted the modal → coerce values and
    complete the task.

  Signature verification uses the raw request body (not the parsed
  form). The route reads the body twice: once as bytes for HMAC, once
  as form data for the payload.

OAuth (`GET /oauth/start` + `GET /oauth/callback`):
  Multi-workspace install flow. `/oauth/start` redirects to Slack's
  consent page with a signed state parameter. `/oauth/callback` verifies
  the state, exchanges the `code` for an access token via `oauth.v2.access`,
  and upserts a SlackInstallation row keyed by team_id. Subsequent posts
  to that workspace read the token from the DB.
"""

from __future__ import annotations

import hmac
import json
import logging
from typing import Any
from urllib.parse import urlencode

import httpx
from fastapi import APIRouter, Cookie, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from awaithumans.forms import FormDefinition
from awaithumans.server.channels.slack.blocks import (
    UnrenderableInSlack,
    form_to_modal,
)
from awaithumans.server.channels.slack.client import get_client_for_team
from awaithumans.server.channels.slack.coerce import slack_values_to_response
from awaithumans.server.channels.slack.oauth_state import sign_state, verify_state
from awaithumans.server.channels.slack.signing import verify_signature
from awaithumans.server.core.config import settings
from awaithumans.server.db.connection import get_session
from awaithumans.server.services.slack_installation_service import (
    upsert_installation,
)
from awaithumans.server.services.task_service import complete_task, get_task
from awaithumans.utils.constants import (
    SLACK_ACTION_OPEN_REVIEW,
    SLACK_DEFAULT_OAUTH_SCOPES,
    SLACK_OAUTH_STATE_MAX_AGE_SECONDS,
)

router = APIRouter(prefix="/channels/slack", tags=["channels"])
logger = logging.getLogger("awaithumans.server.routes.slack")


@router.post("/interactions")
async def slack_interactions(
    request: Request,
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any] | None:
    body = await request.body()

    if not settings.SLACK_SIGNING_SECRET:
        logger.error("Slack interactivity received but SLACK_SIGNING_SECRET unset.")
        raise HTTPException(status_code=503, detail="Slack integration not configured.")

    if not verify_signature(
        body=body,
        timestamp=request.headers.get("X-Slack-Request-Timestamp"),
        signature=request.headers.get("X-Slack-Signature"),
        signing_secret=settings.SLACK_SIGNING_SECRET,
    ):
        logger.warning("Slack interactivity: signature verification failed.")
        raise HTTPException(status_code=401, detail="Invalid Slack signature.")

    form = await request.form()
    raw_payload = form.get("payload")
    if not isinstance(raw_payload, str):
        raise HTTPException(status_code=400, detail="Missing payload.")

    payload = json.loads(raw_payload)
    payload_type = payload.get("type")

    if payload_type == "block_actions":
        await _handle_block_actions(payload, session)
        return None

    if payload_type == "view_submission":
        return await _handle_view_submission(payload, session)

    logger.info("Slack interactivity: ignoring payload type %s", payload_type)
    return None


# ─── block_actions — open the review modal ──────────────────────────────


async def _handle_block_actions(
    payload: dict[str, Any],
    session: AsyncSession,
) -> None:
    actions = payload.get("actions") or []
    open_action = next(
        (a for a in actions if a.get("action_id") == SLACK_ACTION_OPEN_REVIEW),
        None,
    )
    if not open_action:
        return  # Some other button — dashboard link-out etc. — no server work.

    task_id = open_action.get("value")
    trigger_id = payload.get("trigger_id")
    team_id = (payload.get("team") or {}).get("id")
    if not task_id or not trigger_id:
        logger.warning("block_actions: missing task_id or trigger_id.")
        return

    task = await get_task(session, task_id)
    if task.form_definition is None:
        logger.warning("Task %s has no form_definition; cannot open modal.", task_id)
        return

    try:
        form = FormDefinition.model_validate(task.form_definition)
        view = form_to_modal(
            form=form,
            task_id=task.id,
            task_title=task.task,
            task_payload=task.payload,
            redact_payload=task.redact_payload,
        )
    except UnrenderableInSlack as exc:
        logger.warning("Task %s not Slack-renderable: %s", task_id, exc)
        return

    client = await get_client_for_team(session, team_id)
    if client is None:
        logger.error(
            "views.open aborted: no client for team_id=%s (not installed?).",
            team_id,
        )
        return

    await client.views_open(trigger_id=trigger_id, view=view)


# ─── view_submission — complete the task ────────────────────────────────


async def _handle_view_submission(
    payload: dict[str, Any],
    session: AsyncSession,
) -> dict[str, Any]:
    view = payload.get("view") or {}
    task_id = view.get("private_metadata")
    if not task_id:
        raise HTTPException(status_code=400, detail="Missing task_id in modal metadata.")

    user = payload.get("user") or {}
    user_email = user.get("username") or user.get("id")

    task = await get_task(session, task_id)
    if task.form_definition is None:
        raise HTTPException(
            status_code=400,
            detail="Task has no form_definition; cannot coerce submission.",
        )

    form = FormDefinition.model_validate(task.form_definition)
    response = slack_values_to_response(form, view.get("state") or {})

    await complete_task(
        session,
        task_id=task_id,
        response=response,
        completed_by_email=user_email,
        completed_via_channel="slack",
    )

    # Empty response closes the modal successfully.
    return {}


# ─── OAuth install flow ──────────────────────────────────────────────────
#
# Security model:
#
# 1. `/oauth/start` requires `?install_token=X` matching SLACK_INSTALL_TOKEN,
#    compared in constant time. Without this, any visitor who knows PUBLIC_URL
#    could install *their own* workspace into the DB and — if they win the
#    "which install is the default" resolution — receive this server's task
#    notifications. Constant-time compare avoids leaking the token via timing.
# 2. `/oauth/start` also returns 503 when SLACK_BOT_TOKEN is set — that
#    means the operator picked single-workspace mode, so OAuth is off by
#    construction. No way to trick OAuth into running alongside a static token.
# 3. State is cookie-bound. `/oauth/start` sets an httponly+Secure+SameSite=Lax
#    cookie holding the state value; `/oauth/callback` compares the state
#    query param to the cookie (constant-time), then verifies the HMAC
#    signature, then checks expiry. Attacker who signs their own state in
#    their own browser can't forge a matching cookie in the operator's
#    browser.
# 4. Redirect query strings use urlencode() — team_name and error codes
#    from Slack are encoded before landing in the URL.
#
# These defenses assume the operator keeps SLACK_INSTALL_TOKEN secret. For
# public hosted deployments, this install-token scheme needs to be replaced
# with real user auth + per-tenant routing (see BUILD_NOTES §4).


# Name of the cookie holding the OAuth state nonce — read from both routes.
_OAUTH_STATE_COOKIE = "awaithumans_slack_oauth_state"


def _oauth_redirect_uri() -> str:
    return f"{settings.PUBLIC_URL.rstrip('/')}/api/channels/slack/oauth/callback"


def _oauth_scopes() -> str:
    return settings.SLACK_OAUTH_SCOPES or SLACK_DEFAULT_OAUTH_SCOPES


def _oauth_cookie_secure() -> bool:
    """HTTPS-only cookie unless the server is explicitly on plain HTTP (dev)."""
    return settings.PUBLIC_URL.startswith("https://")


def _error_redirect(code: str) -> RedirectResponse:
    """Redirect to dashboard home with a URL-encoded error param."""
    qs = urlencode({"slack_oauth_error": code})
    return RedirectResponse(
        url=f"{settings.PUBLIC_URL.rstrip('/')}/?{qs}"
    )


@router.get("/oauth/start")
async def oauth_start(install_token: str | None = None) -> RedirectResponse:
    """Kick off the Slack OAuth consent flow.

    Requires `?install_token=X` matching AWAITHUMANS_SLACK_INSTALL_TOKEN.
    Without that check, anyone who knows PUBLIC_URL could install their
    own workspace into the server's DB.
    """
    if settings.SLACK_BOT_TOKEN:
        # Single-workspace mode chosen by operator; OAuth must not run.
        raise HTTPException(
            status_code=503,
            detail=(
                "Server is in single-workspace mode (SLACK_BOT_TOKEN is set). "
                "Unset it to enable the OAuth install flow."
            ),
        )
    if (
        not settings.SLACK_CLIENT_ID
        or not settings.SLACK_CLIENT_SECRET
        or not settings.SLACK_SIGNING_SECRET
        or not settings.SLACK_INSTALL_TOKEN
    ):
        raise HTTPException(
            status_code=503,
            detail=(
                "Slack OAuth is not configured. Set "
                "AWAITHUMANS_SLACK_CLIENT_ID, SLACK_CLIENT_SECRET, "
                "SLACK_SIGNING_SECRET, and SLACK_INSTALL_TOKEN."
            ),
        )

    # Operator-only gate. Constant-time compare to avoid token-length leaks.
    if install_token is None or not hmac.compare_digest(
        install_token, settings.SLACK_INSTALL_TOKEN
    ):
        raise HTTPException(status_code=403, detail="Install token required.")

    state = sign_state(settings.SLACK_SIGNING_SECRET)
    params = {
        "client_id": settings.SLACK_CLIENT_ID,
        "scope": _oauth_scopes(),
        "state": state,
        "redirect_uri": _oauth_redirect_uri(),
    }
    response = RedirectResponse(
        url=f"https://slack.com/oauth/v2/authorize?{urlencode(params)}"
    )
    # Double-submit cookie: callback will require this to match the `state`
    # query param Slack sends back.
    response.set_cookie(
        key=_OAUTH_STATE_COOKIE,
        value=state,
        max_age=SLACK_OAUTH_STATE_MAX_AGE_SECONDS,
        httponly=True,
        secure=_oauth_cookie_secure(),
        samesite="lax",
        path="/api/channels/slack/oauth",
    )
    return response


@router.get("/oauth/callback")
async def oauth_callback(
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
    cookie_state: str | None = Cookie(default=None, alias=_OAUTH_STATE_COOKIE),
    session: AsyncSession = Depends(get_session),
) -> RedirectResponse:
    """Finish the OAuth flow: verify state, exchange code, persist tokens."""
    if error:
        return _error_redirect(error[:100])  # cap length defensively

    if not code or not state:
        raise HTTPException(status_code=400, detail="Missing code or state.")

    # 1) State must match the cookie set by /oauth/start. Constant-time.
    #    An attacker who minted a state in their own browser can't set this
    #    cookie in the operator's browser (SameSite=Lax + Secure).
    if not cookie_state or not hmac.compare_digest(state, cookie_state):
        raise HTTPException(status_code=401, detail="OAuth state mismatch.")

    # 2) State must carry a valid HMAC and not be expired.
    if not settings.SLACK_SIGNING_SECRET or not verify_state(
        state, settings.SLACK_SIGNING_SECRET
    ):
        raise HTTPException(status_code=401, detail="Invalid OAuth state.")

    if not settings.SLACK_CLIENT_ID or not settings.SLACK_CLIENT_SECRET:
        raise HTTPException(
            status_code=503, detail="Slack OAuth credentials not configured."
        )

    async with httpx.AsyncClient(timeout=10) as http:
        resp = await http.post(
            "https://slack.com/api/oauth.v2.access",
            data={
                "client_id": settings.SLACK_CLIENT_ID,
                "client_secret": settings.SLACK_CLIENT_SECRET,
                "code": code,
                "redirect_uri": _oauth_redirect_uri(),
            },
        )

    data = resp.json()
    if not data.get("ok"):
        logger.error("Slack oauth.v2.access failed: %s", data.get("error"))
        response = _error_redirect(str(data.get("error", "unknown"))[:100])
        response.delete_cookie(_OAUTH_STATE_COOKIE, path="/api/channels/slack/oauth")
        return response

    team = data.get("team") or {}
    authed_user = data.get("authed_user") or {}
    enterprise = data.get("enterprise") or {}

    team_id = team.get("id")
    bot_token = data.get("access_token")
    bot_user_id = data.get("bot_user_id")
    if not team_id or not bot_token or not bot_user_id:
        logger.error("oauth.v2.access response missing required fields: %s", data)
        raise HTTPException(
            status_code=502, detail="Slack returned an incomplete install response."
        )

    await upsert_installation(
        session,
        team_id=team_id,
        team_name=team.get("name"),
        bot_token=bot_token,
        bot_user_id=bot_user_id,
        scopes=data.get("scope", ""),
        enterprise_id=enterprise.get("id"),
        installed_by_user_id=authed_user.get("id"),
    )
    logger.info("Slack installed for team %s (%s)", team_id, team.get("name"))

    qs = urlencode({"slack_installed": team.get("name") or team_id})
    response = RedirectResponse(
        url=f"{settings.PUBLIC_URL.rstrip('/')}/?{qs}"
    )
    # Single-use cookie — invalidate immediately so replays fail.
    response.delete_cookie(_OAUTH_STATE_COOKIE, path="/api/channels/slack/oauth")
    return response
