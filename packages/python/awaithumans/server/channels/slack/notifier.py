"""Slack task notification — the public entry point from task creation.

Parses the task's `notify` list for Slack routes, resolves the workspace
(static env token, stored OAuth installation, or identity-suffixed
`slack+T123456:#channel` to disambiguate multi-workspace setups), and
posts the initial message.

DM target resolution (`slack:@alice`):
  Slack's `chat.postMessage` only accepts a real user ID (`U…` / `W…`)
  in the `channel` argument; it doesn't resolve handles. So when the
  notify entry is `slack:@alice` we hit `users.list` once, find the
  member by handle, and post to their user_id. Cached per-team for
  the process lifetime so a high-traffic queue doesn't burn the
  `users.list` rate limit. Fallback to `users.lookupByEmail` when
  the target looks like an email.

Runs in a FastAPI BackgroundTask after the response is sent, so a slow
Slack API call never blocks task creation and a Slack outage doesn't
fail a successful task write. The notifier acquires its own DB session
because the caller's session has already been released by the time we run.
"""

from __future__ import annotations

import logging
import re
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

# Slack user IDs are `U…` (regular user) or `W…` (Enterprise Grid).
# Anything else after a `@` is treated as a handle and resolved.
_USER_ID_RE = re.compile(r"^[UW][A-Z0-9]{5,}$")
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

# Per-team cache of (handle → user_id) lookups. Populated lazily on
# first miss; persists for the process lifetime. Slack's user list
# changes rarely; rotating staff is fine — a stale entry just means
# the DM goes to the right person who happens to have a new handle.
# Process restart clears the cache, which is the right invalidation.
_HANDLE_CACHE: dict[str, dict[str, str]] = {}


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

            # Resolve `@handle` / `email` to a real user_id before
            # posting. Slack's chat.postMessage doesn't do handle
            # resolution itself — sending to `@alice` silently fails.
            target = await _resolve_target(
                client=client,
                target=route.target,
                team_id=route.identity,
            )
            if target is None:
                logger.warning(
                    "Slack route %s → could not resolve to a user/channel; "
                    "skipping. Check the handle exists in this workspace.",
                    route.target,
                )
                continue
            try:
                await client.chat_postMessage(
                    channel=target,
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
    return target.startswith(("C", "G"))


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


async def _resolve_target(
    *,
    client: AsyncWebClient,
    target: str,
    team_id: str | None,
) -> str | None:
    """Resolve a notify target to something `chat.postMessage` accepts.

    Channel sigils (`#general`, raw `C…` / `G…` IDs) pass through
    unchanged. User IDs (`@U…`, `U…`) pass through with the leading
    `@` stripped — Slack doesn't want it in the channel argument.
    Anything else after `@` is a handle (`@alice`) and gets resolved
    via `users.list`. Email-shaped targets use `users.lookupByEmail`.

    Returns None when resolution fails (handle not in workspace,
    Slack rejected the call, etc.) — the caller logs and skips."""
    # Channel sigil — broadcast targets pass through unchanged.
    if target.startswith("#"):
        return target

    # Strip the leading `@` if present so we can match against IDs /
    # handles uniformly.
    body = target.removeprefix("@")

    # Already a real user ID? (`U…` / `W…` followed by alnum)
    if _USER_ID_RE.match(body):
        return body

    # Raw channel-ID shape — public, private, or group DM.
    if body.startswith(("C", "G")) and body[1:].isalnum():
        return body

    # Email shape — Slack has a dedicated lookup for that.
    if _EMAIL_RE.match(body):
        return await _resolve_by_email(client=client, email=body, team_id=team_id)

    # Falls through to handle lookup via users.list.
    return await _resolve_by_handle(client=client, handle=body, team_id=team_id)


async def _resolve_by_email(
    *, client: AsyncWebClient, email: str, team_id: str | None
) -> str | None:
    """Use Slack's `users.lookupByEmail` for email-shaped targets.

    Cheaper than walking `users.list` and uses a dedicated endpoint
    that doesn't count against the bulk-list rate limit."""
    try:
        from slack_sdk.errors import SlackApiError

        try:
            resp = await client.users_lookupByEmail(email=email)
        except SlackApiError as exc:
            logger.warning(
                "users.lookupByEmail failed for %s (team=%s): %s",
                email,
                team_id,
                exc.response.get("error", exc),
            )
            return None
    except ImportError:
        logger.error("slack_sdk not installed; can't resolve %s", email)
        return None

    user = resp.get("user") or {}
    user_id = user.get("id")
    return user_id if isinstance(user_id, str) else None


async def _resolve_by_handle(
    *, client: AsyncWebClient, handle: str, team_id: str | None
) -> str | None:
    """Resolve a Slack handle (e.g. `alice`, `alice.singh`) to a user_id.

    Compares against `name`, `profile.display_name`, and
    `profile.real_name` (case-insensitive) so any of the three
    "names" the operator might know works. Caches the lookup table
    per-team for the process lifetime — `users.list` is rate-limited
    and the team rarely changes during a single deploy."""
    cache_key = team_id or "__default__"
    cached = _HANDLE_CACHE.get(cache_key)

    if cached is None:
        cached = await _build_handle_index(client=client, cache_key=cache_key)
        if cached is None:
            return None  # API call failed; logged in helper

    # Match case-insensitively, both with and without leading `@`.
    needle = handle.lstrip("@").lower()
    return cached.get(needle)


async def _build_handle_index(
    *, client: AsyncWebClient, cache_key: str
) -> dict[str, str] | None:
    """Walk `users.list` once, build a {handle_lower: user_id} map.

    Skips bots, deleted users, and the Slackbot pseudo-user. Indexes
    each member by every name field they have so the operator can
    use whichever's familiar."""
    try:
        from slack_sdk.errors import SlackApiError

        try:
            resp = await client.users_list()
        except SlackApiError as exc:
            logger.warning(
                "users.list failed for team=%s: %s",
                cache_key,
                exc.response.get("error", exc),
            )
            return None
    except ImportError:
        logger.error("slack_sdk not installed; handle resolution unavailable")
        return None

    index: dict[str, str] = {}
    for m in resp.get("members", []) or []:
        if m.get("deleted") or m.get("is_bot") or m.get("id") == "USLACKBOT":
            continue
        user_id = m.get("id")
        if not isinstance(user_id, str):
            continue
        # `name` (the @handle), plus the two display fields a user
        # might have set. Case-insensitive lookup so `@Alice` and
        # `@alice` both resolve.
        for raw in (
            m.get("name"),
            (m.get("profile") or {}).get("display_name"),
            (m.get("profile") or {}).get("real_name"),
        ):
            if isinstance(raw, str) and raw:
                index[raw.lower()] = user_id

    _HANDLE_CACHE[cache_key] = index
    logger.info(
        "Indexed %d Slack handles for team=%s (cached for process lifetime)",
        len(index),
        cache_key,
    )
    return index
