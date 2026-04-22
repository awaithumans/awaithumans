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
from typing import TYPE_CHECKING, Any

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

if TYPE_CHECKING:  # pragma: no cover
    from slack_sdk.web.async_client import AsyncWebClient

from awaithumans.forms import FormDefinition
from awaithumans.server.channels.slack.blocks import (
    UnrenderableInSlackError,
    claimed_message_blocks,
    form_to_modal,
)
from awaithumans.server.channels.slack.client import get_client_for_team
from awaithumans.server.channels.slack.coerce import slack_values_to_response
from awaithumans.server.channels.slack.signing import verify_signature
from awaithumans.server.core.config import settings
from awaithumans.server.db.connection import get_session
from awaithumans.server.services.exceptions import (
    TaskAlreadyClaimedError,
    TaskAlreadyTerminalError,
)
from awaithumans.server.services.task_service import (
    claim_task,
    complete_task,
    get_task,
)
from awaithumans.server.services.user_service import get_user, get_user_by_slack
from awaithumans.utils.constants import (
    SLACK_ACTION_CLAIM_TASK,
    SLACK_ACTION_OPEN_REVIEW,
)

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

    # Claim-first path: broadcast-to-channel messages show a "Claim"
    # button. First clicker wins atomically, then the modal opens for
    # them. Claim has priority over open-review so a broadcast message
    # with both buttons is disambiguated.
    claim_action = next(
        (a for a in actions if a.get("action_id") == SLACK_ACTION_CLAIM_TASK),
        None,
    )
    if claim_action:
        await _handle_claim(payload, claim_action, session)
        return

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

    await _open_modal_for_task(
        session=session,
        task_id=task_id,
        trigger_id=trigger_id,
        team_id=team_id,
    )


async def _open_modal_for_task(
    *,
    session: AsyncSession,
    task_id: str,
    trigger_id: str,
    team_id: str | None,
) -> None:
    """Load the task, build the modal, open it via `views.open`.

    Shared between the direct "Open in Slack" button (DM flow) and the
    post-claim modal pop (channel broadcast flow).
    """
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


async def _handle_claim(
    payload: dict[str, Any],
    action: dict[str, Any],
    session: AsyncSession,
) -> None:
    """Handle a "Claim this task" click from a broadcast channel message.

    Flow:
      1. Resolve the Slack user to a directory user (by team_id + slack_user_id).
         Users who aren't in the directory get an ephemeral "ask your operator
         to add you" reply — enforces directory hygiene so claims correlate
         cleanly with the routing model.
      2. Atomic claim on the task — first click wins. Second click gets an
         ephemeral "already claimed by ..." reply.
      3. Update the channel message to show who claimed it (hides the
         button for everyone else).
      4. Open the response modal for the claimer.
    """
    task_id = action.get("value")
    trigger_id = payload.get("trigger_id")
    team = payload.get("team") or {}
    team_id = team.get("id")
    user = payload.get("user") or {}
    slack_user_id = user.get("id")
    slack_username = user.get("username") or user.get("name")
    response_url = payload.get("response_url")
    channel = (payload.get("channel") or {}).get("id")
    message = payload.get("message") or {}
    message_ts = message.get("ts")

    if not task_id or not trigger_id or not team_id or not slack_user_id:
        logger.warning(
            "claim: missing field (task_id=%s, trigger_id=%s, team=%s, user=%s)",
            task_id, trigger_id, team_id, slack_user_id,
        )
        return

    client = await get_client_for_team(session, team_id)
    if client is None:
        logger.error("claim: no client for team_id=%s", team_id)
        return

    directory_user = await get_user_by_slack(
        session, slack_team_id=team_id, slack_user_id=slack_user_id
    )
    if directory_user is None or not directory_user.active:
        await _ephemeral_reply(
            client=client,
            channel=channel,
            user_id=slack_user_id,
            response_url=response_url,
            text=(
                "You're not in this server's user directory. "
                "Ask your operator to add you via Settings → Users, "
                "then try claiming again."
            ),
        )
        return

    try:
        task = await claim_task(
            session,
            task_id=task_id,
            user_id=directory_user.id,
            user_email=directory_user.email,
            claimed_via_channel="slack",
        )
    except TaskAlreadyClaimedError as exc:
        claimer_display = await _display_for_user_id(session, exc.claimed_by_user_id)
        await _ephemeral_reply(
            client=client,
            channel=channel,
            user_id=slack_user_id,
            response_url=response_url,
            text=f"Already claimed by {claimer_display}.",
        )
        return
    except TaskAlreadyTerminalError:
        await _ephemeral_reply(
            client=client,
            channel=channel,
            user_id=slack_user_id,
            response_url=response_url,
            text="This task is already completed or cancelled.",
        )
        return

    # Message update: swap the card for a "Claimed by X" state so the
    # button vanishes for the rest of the channel. Best-effort — if
    # chat.update fails (lost permissions, message deleted) we still
    # pop the modal for the claimer.
    claimer_display = (
        f"<@{slack_user_id}>"
        if slack_user_id
        else directory_user.display_name or directory_user.email or "a user"
    )
    review_url = f"{settings.PUBLIC_URL.rstrip('/')}/task?id={task.id}"
    if channel and message_ts:
        try:
            await client.chat_update(
                channel=channel,
                ts=message_ts,
                text=f"Claimed by {slack_username or 'a user'}: {task.task}",
                blocks=claimed_message_blocks(
                    task_title=task.task,
                    review_url=review_url,
                    claimed_by_display=claimer_display,
                ),
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("chat.update after claim failed: %s", exc)

    # Pop the modal for the claimer so they can complete it immediately.
    await _open_modal_for_task(
        session=session,
        task_id=task.id,
        trigger_id=trigger_id,
        team_id=team_id,
    )


async def _display_for_user_id(
    session: AsyncSession, user_id: str | None
) -> str:
    """Human-readable label for the user who won a claim race."""
    if not user_id:
        return "another user"
    user = await get_user(session, user_id)
    if user is None:
        return "another user"
    if user.slack_user_id:
        return f"<@{user.slack_user_id}>"
    return user.display_name or user.email or "another user"


async def _ephemeral_reply(
    *,
    client: AsyncWebClient,
    channel: str | None,
    user_id: str,
    response_url: str | None,
    text: str,
) -> None:
    """Post an ephemeral message to the clicker.

    Uses response_url when we have it (works even without chat:write to
    the channel) and falls back to chat.postEphemeral for private
    channels where response_url isn't useful.
    """
    if response_url:
        try:
            await client.api_call(
                "",
                http_verb="POST",
                json={"response_type": "ephemeral", "text": text},
                url=response_url,
            )
            return
        except Exception as exc:  # noqa: BLE001
            logger.warning("ephemeral via response_url failed: %s", exc)

    if channel:
        try:
            await client.chat_postEphemeral(
                channel=channel, user=user_id, text=text
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("chat.postEphemeral failed: %s", exc)


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
