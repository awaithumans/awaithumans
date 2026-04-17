"""Slack API request/response schemas.

`bot_token` is NEVER part of a response model — it's stored encrypted
and only read server-side by notifier.py. The public shape only
carries enough to recognise which workspace an installation is.
"""

from __future__ import annotations

from pydantic import BaseModel


class SlackInstallationResponse(BaseModel):
    team_id: str
    team_name: str | None
    bot_user_id: str
    scopes: str
    enterprise_id: str | None
    installed_by_user_id: str | None
    installed_at: str
    updated_at: str

    model_config = {"from_attributes": True}
