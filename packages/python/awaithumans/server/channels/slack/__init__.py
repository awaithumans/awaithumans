"""Slack channel — Block Kit rendering + interactivity handling.

Public API (used by the app factory and task routes):

    from awaithumans.server.channels.slack import (
        form_to_modal,
        slack_values_to_response,
        verify_signature,
        notify_task,
    )

The bot token and signing secret come from `server/core/config.py`. If
either is missing, Slack is disabled and notify("slack:...") entries
produce a warning log.
"""

from __future__ import annotations

from awaithumans.server.channels.slack.blocks import form_to_modal
from awaithumans.server.channels.slack.client import (
    get_client_for_team,
    get_default_client,
    get_env_client,
)
from awaithumans.server.channels.slack.coerce import slack_values_to_response
from awaithumans.server.channels.slack.notifier import notify_task
from awaithumans.server.channels.slack.oauth_state import sign_state, verify_state
from awaithumans.server.channels.slack.signing import verify_signature

__all__ = [
    "form_to_modal",
    "get_client_for_team",
    "get_default_client",
    "get_env_client",
    "notify_task",
    "sign_state",
    "slack_values_to_response",
    "verify_signature",
    "verify_state",
]
