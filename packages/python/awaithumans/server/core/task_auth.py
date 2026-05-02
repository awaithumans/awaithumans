"""Per-task authorization helpers.

Three callers can legitimately touch a task:

  - **Admin bearer token** (the agent process, ops scripts, CI). Trusted
    fully — bypasses every check below.
  - **Operator session** (a logged-in user with `is_operator=True`).
    Can read/list/complete/cancel any task.
  - **Assignee session** (a logged-in user whose ID matches
    `task.assigned_to_user_id`). Can only see and complete the tasks
    routed to them.

Anyone else (a logged-in non-operator who isn't the assignee) is
forbidden.

The helpers in this module are deliberately small and ortho­gonal so
they compose into route handlers without ballooning them. The
middleware (`core/auth.py`) already performs base authentication;
these helpers add the per-task authorisation layer on top.
"""

from __future__ import annotations

from fastapi import HTTPException, Request

from awaithumans.server.core.auth import SessionClaims
from awaithumans.server.db.models import Task


def _is_admin_bearer(request: Request) -> bool:
    """Admin bearer token caller — set by the auth middleware."""
    return bool(getattr(request.state, "auth_admin_token", False))


def _session_claims(request: Request) -> SessionClaims | None:
    claims = getattr(request.state, "auth_claims", None)
    return claims if isinstance(claims, SessionClaims) else None


def caller_is_operator(request: Request) -> bool:
    """True when the caller has a session with `is_operator=True`.

    Admin bearer is intentionally NOT counted as operator here — use
    `_is_admin_bearer` separately when the route should accept either."""
    claims = _session_claims(request)
    return claims is not None and claims.is_operator


def caller_user_id(request: Request) -> str | None:
    """The directory user ID of the caller, if cookie-authenticated.

    Returns None for admin-bearer callers (no user identity) and for
    unauthenticated requests (which the middleware would have rejected
    already)."""
    claims = _session_claims(request)
    return claims.user_id if claims is not None else None


def require_task_read(request: Request, task: Task) -> None:
    """Allow if admin / operator / the task's assignee. Otherwise 403.

    Used by GET routes that surface task data — payload, response,
    audit. Non-operators must not be able to enumerate other people's
    tasks; the `assigned_to_user_id == claims.user_id` check is the
    single source of authorisation."""
    if _is_admin_bearer(request):
        return
    if caller_is_operator(request):
        return
    user_id = caller_user_id(request)
    if user_id is not None and task.assigned_to_user_id == user_id:
        return
    raise HTTPException(
        status_code=403,
        detail="You don't have access to this task.",
    )


def require_task_complete(request: Request, task: Task) -> None:
    """Same allow-list as `require_task_read`.

    Kept as a separate function so future divergence (e.g. operators
    can read but only assignees can complete) doesn't require chasing
    callers."""
    require_task_read(request, task)


def require_operator_or_admin(request: Request) -> None:
    """Allow only operators and admin-bearer callers. 403 otherwise.

    Used for: cancel (agent path), poll (agent path), audit (operator
    review), list (when the caller wants to see all tasks). The
    parallel `require_admin` dependency in `core/admin_auth.py` is for
    pure admin surfaces; this one accepts any operator session too."""
    if _is_admin_bearer(request):
        return
    if caller_is_operator(request):
        return
    raise HTTPException(
        status_code=403,
        detail="Operator access required.",
    )
