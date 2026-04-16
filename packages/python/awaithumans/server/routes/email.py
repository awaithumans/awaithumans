"""Email channel routes — admin identity CRUD + magic-link action endpoints.

Admin endpoints (protected by AWAITHUMANS_ADMIN_API_TOKEN via the
`require_admin` dep):

    POST   /api/channels/email/identities         — create/update
    GET    /api/channels/email/identities         — list
    GET    /api/channels/email/identities/{id}    — fetch one
    DELETE /api/channels/email/identities/{id}    — remove

Public action endpoints (token-signed, no auth required):

    GET    /api/channels/email/action/{token}     — anti-prefetch confirm page
    POST   /api/channels/email/action/{token}     — actually complete the task

The magic-link token carries (task_id, field_name, value, expiry) signed
with an HMAC key derived from PAYLOAD_KEY. GET is safe to prefetch — it
only renders a form. POST mutates state.
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Path
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from awaithumans.server.channels.email.magic_links import (
    InvalidActionToken,
    verify_action_token,
)
from awaithumans.server.channels.email.templates import (
    completed_page_html,
    confirmation_page_html,
)
from awaithumans.server.channels.email.transport import (
    EmailTransportError,
    resolve_transport,
)
from awaithumans.server.core.admin_auth import require_admin
from awaithumans.server.db.connection import get_session
from awaithumans.server.services.email_identity_service import (
    delete_identity,
    get_identity,
    identity_config,
    list_identities,
    upsert_identity,
)
from awaithumans.server.services.exceptions import TaskAlreadyTerminalError
from awaithumans.server.services.task_service import complete_task, get_task

router = APIRouter(prefix="/channels/email", tags=["channels"])
logger = logging.getLogger("awaithumans.server.routes.email")


# ─── Admin: identity CRUD ────────────────────────────────────────────────


class IdentityCreateRequest(BaseModel):
    id: str = Field(min_length=1, max_length=100)
    display_name: str
    from_email: str
    from_name: str | None = None
    reply_to: str | None = None
    transport: str                    # "resend" | "smtp" | "logging" | "noop"
    transport_config: dict[str, Any]  # kind-specific (api_key, host, port, ...)


class IdentityResponse(BaseModel):
    """Public view of an identity — NEVER includes transport_config.

    The decrypted config lives in the DB + service layer only. Even admins
    can't read it back via the API — if someone needs to rotate a key, they
    POST a new identity config (upsert). This prevents an attacker who
    steals the admin token from exfiltrating provider credentials en masse.
    """

    id: str
    display_name: str
    from_email: str
    from_name: str | None
    reply_to: str | None
    transport: str
    verified: bool
    verified_at: str | None

    model_config = {"from_attributes": True}


def _to_public(row: Any) -> IdentityResponse:
    return IdentityResponse(
        id=row.id,
        display_name=row.display_name,
        from_email=row.from_email,
        from_name=row.from_name,
        reply_to=row.reply_to,
        transport=row.transport,
        verified=row.verified,
        verified_at=row.verified_at.isoformat() if row.verified_at else None,
    )


@router.post(
    "/identities",
    response_model=IdentityResponse,
    dependencies=[Depends(require_admin)],
)
async def create_identity(
    body: IdentityCreateRequest,
    session: AsyncSession = Depends(get_session),
) -> IdentityResponse:
    """Create or update an email sender identity.

    Validates the transport config by building the transport. A bad
    config raises 400 here rather than failing silently later.
    """
    try:
        resolve_transport(body.transport, body.transport_config)
    except EmailTransportError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    row = await upsert_identity(
        session,
        identity_id=body.id,
        display_name=body.display_name,
        from_email=body.from_email,
        from_name=body.from_name,
        reply_to=body.reply_to,
        transport=body.transport,
        transport_config=body.transport_config,
    )
    return _to_public(row)


@router.get(
    "/identities",
    response_model=list[IdentityResponse],
    dependencies=[Depends(require_admin)],
)
async def list_email_identities(
    session: AsyncSession = Depends(get_session),
) -> list[IdentityResponse]:
    rows = await list_identities(session)
    return [_to_public(r) for r in rows]


@router.get(
    "/identities/{identity_id}",
    response_model=IdentityResponse,
    dependencies=[Depends(require_admin)],
)
async def get_email_identity(
    identity_id: str,
    session: AsyncSession = Depends(get_session),
) -> IdentityResponse:
    row = await get_identity(session, identity_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Identity not found.")
    return _to_public(row)


@router.delete(
    "/identities/{identity_id}",
    status_code=204,
    response_class=HTMLResponse,  # HTMLResponse supports empty body; default JSONResponse does not
    dependencies=[Depends(require_admin)],
)
async def delete_email_identity(
    identity_id: str,
    session: AsyncSession = Depends(get_session),
) -> HTMLResponse:
    if not await delete_identity(session, identity_id):
        raise HTTPException(status_code=404, detail="Identity not found.")
    return HTMLResponse(status_code=204)


# ─── Magic-link action (public, token-signed) ───────────────────────────


def _confirm_page(claim: Any, post_url: str, task_title: str) -> HTMLResponse:
    # Humanize the value for the button label.
    v = claim.value
    if v is True:
        label = "Yes"
    elif v is False:
        label = "No"
    else:
        label = str(v)
    cancel_url = "/"
    return HTMLResponse(
        content=confirmation_page_html(
            task_title=task_title,
            action_label=label,
            post_url=post_url,
            cancel_url=cancel_url,
        )
    )


@router.get(
    "/action/{token}",
    response_class=HTMLResponse,
    include_in_schema=False,
)
async def action_confirm(
    token: str = Path(...),
    session: AsyncSession = Depends(get_session),
) -> HTMLResponse:
    """Render the 'Are you sure?' page for a magic-link click.

    GET is safe to prefetch — nothing changes state here. A POST from
    the rendered form is what actually completes the task.
    """
    try:
        claim = verify_action_token(token)
    except InvalidActionToken as exc:
        logger.info("Magic-link GET rejected: %s", exc)
        return HTMLResponse(
            status_code=400,
            content=completed_page_html(
                message=(
                    "This link is invalid or has expired. "
                    "Open the dashboard to review the task instead."
                )
            ),
        )

    try:
        task = await get_task(session, claim.task_id)
    except Exception:
        return HTMLResponse(
            status_code=404,
            content=completed_page_html(
                message="The task linked to this email no longer exists."
            ),
        )

    from awaithumans.utils.constants import TERMINAL_STATUSES_SET

    if task.status in TERMINAL_STATUSES_SET:
        return HTMLResponse(
            content=completed_page_html(
                message=f"This task was already {task.status.value.replace('_', ' ')}."
            )
        )

    return _confirm_page(
        claim, post_url=f"/api/channels/email/action/{token}", task_title=task.task
    )


@router.post(
    "/action/{token}",
    response_class=HTMLResponse,
    include_in_schema=False,
)
async def action_submit(
    token: str = Path(...),
    session: AsyncSession = Depends(get_session),
) -> HTMLResponse:
    """Actually complete the task from a magic-link confirmation."""
    try:
        claim = verify_action_token(token)
    except InvalidActionToken as exc:
        logger.info("Magic-link POST rejected: %s", exc)
        return HTMLResponse(
            status_code=400,
            content=completed_page_html(
                message="This link is invalid or has expired."
            ),
        )

    try:
        await complete_task(
            session,
            task_id=claim.task_id,
            response={claim.field_name: claim.value},
            completed_by_email=None,
            completed_via_channel="email",
        )
    except TaskAlreadyTerminalError:
        return HTMLResponse(
            content=completed_page_html(
                message="This task was already completed."
            )
        )

    return HTMLResponse(
        content=completed_page_html(
            message="Response recorded. Thanks for reviewing."
        )
    )
