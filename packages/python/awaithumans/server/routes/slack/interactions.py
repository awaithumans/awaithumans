"""Slack interactivity webhook — `POST /interactions`.

Slack POSTs here for every button click and modal submission. The body
is `application/x-www-form-urlencoded` with a single `payload` field
whose value is a JSON string. Two payload shapes are handled:

- `block_actions`: user clicked the "Open in Slack" button on the
  initial message → open a modal via `views.open`.
- `view_submission`: user submitted the modal → coerce values and
  complete the task.

Signature verification uses the raw request body (not the parsed form).
The route reads the body twice: once as bytes for HMAC, once as form
data for the payload.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from awaithumans.forms import FormDefinition
from awaithumans.server.channels.slack.blocks import (
    UnrenderableInSlackError,
    form_to_modal,
)
from awaithumans.server.channels.slack.client import get_client_for_team
from awaithumans.server.channels.slack.coerce import slack_values_to_response
from awaithumans.server.channels.slack.signing import verify_signature
from awaithumans.server.core.config import settings
from awaithumans.server.db.connection import get_session
from awaithumans.server.services.task_service import complete_task, get_task
from awaithumans.utils.constants import SLACK_ACTION_OPEN_REVIEW

router = APIRouter()
logger = logging.getLogger("awaithumans.server.routes.slack.interactions")


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
    except UnrenderableInSlackError as exc:
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
