"""Auth API request/response schemas.

Split out from routes/auth.py so routes carry handlers only.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    email: str = Field(min_length=1, max_length=320, description="User's email address.")
    password: str = Field(min_length=1, max_length=200)


class MeResponse(BaseModel):
    authenticated: bool
    user_id: str | None = None
    email: str | None = None
    display_name: str | None = None
    is_operator: bool = False
