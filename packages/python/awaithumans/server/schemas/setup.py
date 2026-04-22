"""First-run setup API request/response schemas.

Split out from routes/setup.py so routes carry handlers only.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class SetupStatusResponse(BaseModel):
    """Tells the dashboard which landing page to show."""

    needs_setup: bool
    # `token_active` is true only while a bootstrap token exists in the
    # server's memory. The actual token is never returned; operators read
    # it from the server log. This field just lets the /setup page
    # distinguish "server is ready, paste your token" from "already done."
    token_active: bool


class CreateOperatorRequest(BaseModel):
    token: str = Field(min_length=1)
    email: str = Field(min_length=1, max_length=320)
    password: str = Field(min_length=8)
    display_name: str | None = None


class CreateOperatorResponse(BaseModel):
    user_id: str
    email: str
