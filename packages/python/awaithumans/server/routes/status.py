"""System status route — GET /api/status.

Returns diagnostic data the operator wants visible on the Settings page:
which channels are configured, whether encryption is on, which mode of
Slack is active. No secrets, no keys, no passwords ever leave the server.

Gated by the dashboard auth middleware — probes from the public internet
return 401 when `DASHBOARD_PASSWORD` is set.
"""

from __future__ import annotations

from fastapi import APIRouter

from awaithumans.server.core.config import settings
from awaithumans.server.schemas.status import SystemStatus

router = APIRouter(prefix="/status", tags=["status"])


def _slack_mode() -> str:
    if settings.SLACK_BOT_TOKEN:
        return "single-workspace"
    if settings.SLACK_CLIENT_ID and settings.SLACK_CLIENT_SECRET:
        return "multi-workspace"
    return "off"


@router.get("", response_model=SystemStatus)
async def get_status() -> SystemStatus:
    return SystemStatus(
        version="0.1.0",
        environment=settings.ENVIRONMENT,
        public_url=settings.PUBLIC_URL,
        auth_enabled=bool(settings.DASHBOARD_PASSWORD),
        payload_encryption_enabled=bool(settings.PAYLOAD_KEY),
        admin_token_enabled=bool(settings.ADMIN_API_TOKEN),
        slack_mode=_slack_mode(),
        email_transport=settings.EMAIL_TRANSPORT,
        email_from=settings.EMAIL_FROM,
    )
