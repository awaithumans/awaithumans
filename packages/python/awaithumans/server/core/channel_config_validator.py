"""Boot-time validation that a half-configured channel doesn't fail silently.

Operators frequently set the "primary" env var for a channel
(`EMAIL_TRANSPORT=smtp`, `SLACK_BOT_TOKEN=...`) and forget the
matching credentials. With the silent-drop behavior the SDK had pre-
v0.1.4 (now surfaced via `notification_failed` audit entries +
banner), the operator never knew until the first delivery silently
failed and the human never reviewed. This module catches the
misconfiguration at server start and emits a single WARNING per
channel listing the missing env vars.

Called once from `create_app()` after `setup_logging()` so warnings
land through the configured formatter alongside the rest of the
startup log.
"""

from __future__ import annotations

import logging

from awaithumans.server.core.config import Settings

logger = logging.getLogger("awaithumans.server.core.channel_config")


def validate_channel_config(settings: Settings) -> None:
    """Emit one WARNING per partially-configured channel. Never raises.

    The runtime is still functional with a partial config — sends just
    fail (now visibly, via the notification_failed audit + banner).
    Boot-time logs make the misconfig obvious before the first task.
    """
    _validate_email(settings)
    _validate_slack(settings)


def _validate_email(settings: Settings) -> None:
    transport = (settings.EMAIL_TRANSPORT or "").lower()
    if not transport:
        return

    if transport == "smtp":
        required = {
            "AWAITHUMANS_SMTP_HOST": settings.SMTP_HOST,
            "AWAITHUMANS_SMTP_USER": settings.SMTP_USER,
            "AWAITHUMANS_SMTP_PASSWORD": settings.SMTP_PASSWORD,
            "AWAITHUMANS_EMAIL_FROM": settings.EMAIL_FROM,
        }
        missing = [k for k, v in required.items() if not v]
        if missing:
            logger.warning(
                "AWAITHUMANS_EMAIL_TRANSPORT=smtp is set but these env vars "
                "are missing: %s. SMTP sends will fail with %s until they're "
                "configured.",
                ", ".join(missing),
                "no_from_address" if missing == ["AWAITHUMANS_EMAIL_FROM"] else "transport_error",
            )
        return

    if transport == "resend":
        required = {
            "AWAITHUMANS_RESEND_KEY": settings.RESEND_KEY,
            "AWAITHUMANS_EMAIL_FROM": settings.EMAIL_FROM,
        }
        missing = [k for k, v in required.items() if not v]
        if missing:
            logger.warning(
                "AWAITHUMANS_EMAIL_TRANSPORT=resend is set but these env vars "
                "are missing: %s. Resend sends will fail until they're "
                "configured.",
                ", ".join(missing),
            )
        return

    # `logging` and `noop` transports need no credentials. Anything
    # else is an unknown transport name — surface that too.
    if transport not in ("logging", "noop"):
        logger.warning(
            "AWAITHUMANS_EMAIL_TRANSPORT=%s is not a recognized transport. "
            "Expected one of: smtp, resend, logging, noop.",
            transport,
        )


def _validate_slack(settings: Settings) -> None:
    # Single-workspace mode: static bot token, no OAuth.
    if settings.SLACK_BOT_TOKEN and not settings.SLACK_SIGNING_SECRET:
        logger.warning(
            "AWAITHUMANS_SLACK_BOT_TOKEN is set but "
            "AWAITHUMANS_SLACK_SIGNING_SECRET is missing. Outbound Slack "
            "messages will send, but inbound interactions (claim buttons, "
            "modal submits) will fail signature verification."
        )

    # OAuth multi-workspace mode: client_id, client_secret, install_token,
    # signing_secret all required together.
    if settings.SLACK_CLIENT_ID:
        required = {
            "AWAITHUMANS_SLACK_CLIENT_SECRET": settings.SLACK_CLIENT_SECRET,
            "AWAITHUMANS_SLACK_SIGNING_SECRET": settings.SLACK_SIGNING_SECRET,
            "AWAITHUMANS_SLACK_INSTALL_TOKEN": settings.SLACK_INSTALL_TOKEN,
        }
        missing = [k for k, v in required.items() if not v]
        if missing:
            logger.warning(
                "AWAITHUMANS_SLACK_CLIENT_ID is set (OAuth multi-workspace "
                "mode) but these env vars are missing: %s. The OAuth install "
                "flow at /api/channels/slack/oauth/start will fail.",
                ", ".join(missing),
            )
