"""User directory API request/response schemas.

Public responses NEVER include `password_hash`. The hash stays in the
DB and the service layer; even operators can't read it back via the
API — same discipline as email `transport_config`.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class UserCreateRequest(BaseModel):
    """Create a user. At least one of `email` or the slack pair must be set —
    validation happens in the service layer (the DB can't express
    "at least one of these two fields" portably)."""

    display_name: str | None = None

    email: str | None = None
    slack_team_id: str | None = None
    slack_user_id: str | None = None

    role: str | None = None
    access_level: str | None = None
    pool: str | None = None

    is_operator: bool = False
    # Set this only if the user is expected to log into the dashboard.
    # Leave null for Slack-only or email-only reviewers who never see
    # the dashboard directly.
    password: str | None = Field(default=None, min_length=8)

    active: bool = True


class UserUpdateRequest(BaseModel):
    """Partial update. Null fields are left unchanged; to clear a field,
    pass an empty string (for text fields) or false (for booleans).

    `password`: pass a non-null string to set a new password. Pass null
    to leave the current one alone. Use DELETE /api/admin/users/{id}/password
    to explicitly clear it.
    """

    display_name: str | None = None

    email: str | None = None
    slack_team_id: str | None = None
    slack_user_id: str | None = None

    role: str | None = None
    access_level: str | None = None
    pool: str | None = None

    is_operator: bool | None = None
    password: str | None = Field(default=None, min_length=8)
    active: bool | None = None


class UserResponse(BaseModel):
    """Public view of a user. Omits `password_hash` and raw timestamps
    are emitted as ISO strings."""

    id: str
    display_name: str | None

    email: str | None
    slack_team_id: str | None
    slack_user_id: str | None

    role: str | None
    access_level: str | None
    pool: str | None

    is_operator: bool
    has_password: bool  # surfaces "can this user log in?" without leaking the hash

    active: bool
    last_assigned_at: datetime | None

    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class SetPasswordRequest(BaseModel):
    password: str = Field(min_length=8)
