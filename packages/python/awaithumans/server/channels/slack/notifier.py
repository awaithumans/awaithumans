"""Slack task notification — the public entry point from task creation.

Parses the task's `notify` list for Slack routes, resolves the workspace
(static env token, stored OAuth installation, or identity-suffixed
`slack+T123456:#channel` to disambiguate multi-workspace setups), and
posts the initial message.

Runs in a FastAPI BackgroundTask after the response is sent, so a slow
Slack API call never blocks task creation and a Slack outage doesn't
fail a successful task write. The notifier acquires its own DB session
because the caller's session has already been released by the time we run.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from awaithumans.forms import FormDefinition, unsupported_fields
from awaithumans.server.channels.routing import ChannelRoute, routes_for_channel
from awaithumans.server.channels.slack.blocks import open_review_message_blocks
from awaithumans.server.channels.slack.client import (
    get_client_for_team,
    get_default_client,
)
from awaithumans.server.core.config import settings
from awaithumans.server.db.connection import get_async_session_factory
from awaithumans.utils.constants import (
    SLACK_ACTION_CLAIM_TASK,
    SLACK_ACTION_OPEN_REVIEW,
)

if TYPE_CHECKING:  # pragma: no cover
    from slack_sdk.web.async_client import AsyncWebClient
    from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger("awaithumans.server.channels.slack.notifier")


async def notify_task(
    *,
    task_id: str,
    task_title: str,
    notify: list[str] | None,
    form_definition: dict[str, Any] | None,
) -> None:
    """Post the initial Slack message to every slack: route on the task."""
    routes = routes_for_channel(notify, "slack")
    if not routes:
        return

    form = _parse_form(form_definition)
    # The dashboard moved to `/task?id=…` for static-export compatibility
    # (dynamic segments don't survive `output: "export"`). Old `/tasks/{id}`
    # 404s.
    review_url = f"{settings.PUBLIC_URL.rstrip('/')}/task?id={task_id}"
    offenders = unsupported_fields(form, "slack") if form is not None else None
    fallback_text = f"New task: {task_title}"

    factory = get_async_session_factory()
    async with factory() as session:
        for route in routes:
            # Broadcast: route target starts with `#` → posting to a
            # channel where anyone could pick it up. Swap the "Open in
            # Slack" button for "Claim this task" — first clicker wins.
            # DM targets (`@user` / `U123456`) stay on the direct-open
            # flow since the recipient is already implied.
            broadcast = _is_channel_target(route.target)

            blocks = open_review_message_blocks(
                task_id=task_id,
                task_title=task_title,
                review_url=review_url,
                open_button_action_id=SLACK_ACTION_OPEN_REVIEW,
                unsupported_fields=offenders if offenders else None,
                broadcast=broadcast,
                claim_button_action_id=SLACK_ACTION_CLAIM_TASK,
            )

            client = await _resolve_client(session, route)
            if client is None:
                logger.warning(
                    "Slack route %s → no client (identity=%s); skipping.",
                    route.target,
                    route.identity,
                )
                continue
            try:
                await client.chat_postMessage(
                    channel=route.target,
                    text=fallback_text,
                    blocks=blocks,
                )
                logger.info(
                    "Slack notification sent for task %s → %s%s%s",
                    task_id,
                    route.target,
                    f" (team={route.identity})" if route.identity else "",
                    " [broadcast]" if broadcast else "",
                )
            except Exception as exc:  # noqa: BLE001
                logger.error(
                    "Slack notification failed for task %s → %s: %s",
                    task_id,
                    route.target,
                    exc,
                )


def _is_channel_target(target: str) -> bool:
    """`#channel` names are broadcasts; `@user` and raw user IDs are DMs.

    Slack uses `#` as the channel sigil across chat and the API. Raw
    channel IDs (`C01ABC234`) are also broadcasts; we detect those
    conservatively by checking the first char — `C` (public/private
    channel) or `G` (group DM). User IDs start with `U` or `W`.
    """
    if not target:
        return False
    if target.startswith("#"):
        return True
    if target.startswith(("C", "G")):
        return True
    return False


async def _resolve_client(
    session: AsyncSession, route: ChannelRoute
) -> AsyncWebClient | None:
    if route.identity:
        # identity-suffixed route: pick exactly that workspace, no fallback.
        return await get_client_for_team(session, route.identity)
    return await get_default_client(session)


def _parse_form(form_definition: dict[str, Any] | None) -> FormDefinition | None:
    if not form_definition:
        return None
    try:
        return FormDefinition.model_validate(form_definition)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Invalid form_definition on task: %s", exc)
        return None
