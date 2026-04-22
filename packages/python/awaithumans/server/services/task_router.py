"""Task routing — resolve `assign_to` dict to a concrete user (Option C).

Three input shapes, resolved in priority order:

1. `assign_to = {"email": "..."}` — exact address. Router looks the
   user up to find the stable `user_id`, but falls through to
   "user not in directory" as a soft path (developer is being
   explicit; we trust them even without a matching user row). The
   task still gets `assigned_to_email` set.

2. `assign_to = {"role": "...", "access_level": "...", "pool": "..."}`
   — filter attributes. Router queries active users matching the
   filters and picks the **least recently assigned** one. That user's
   `last_assigned_at` is bumped in the same transaction so two
   concurrent tasks pick different users (single-writer SQLite) or
   race safely (Postgres — last committer wins on the row, second
   pick reads the fresh timestamp).

3. `assign_to = None` OR no matching user — task stays unassigned
   (`assigned_to_email = None`, `assigned_to_user_id = None`). The
   operator can assign it manually from the dashboard, or a broadcast
   channel (PR B) can be claimed by whoever picks it up first.

Notification semantics (read by the channels layer):

- If a user was resolved and `notify` is empty, the channels layer
  emits to all of the user's registered addresses (email if set,
  slack if set).
- If `notify` is provided explicitly, it's a complete override —
  nothing is auto-derived from the resolved user.

The router does NOT mutate the task row directly. It returns a dict
describing the resolution; `create_task` applies it. Keeps the router
testable independent of the task service.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from awaithumans.server.db.models import User

logger = logging.getLogger("awaithumans.server.services.task_router")


@dataclass(frozen=True)
class RoutingResult:
    """What the router decided. Mirrors the fields `create_task` needs
    to set on the new task row."""

    user_id: str | None
    email: str | None
    # Not set on the task directly; returned for the channels layer
    # to consult when `notify` was empty and the router had to pick
    # implicit delivery addresses.
    slack_team_id: str | None = None
    slack_user_id: str | None = None


async def resolve_assign_to(
    session: AsyncSession,
    assign_to: dict[str, Any] | None,
) -> RoutingResult:
    """Resolve `assign_to` to a concrete user reference.

    Does NOT commit — caller is responsible for transaction boundaries.
    A successful role-based match bumps `last_assigned_at` on the picked
    user in the caller's transaction so fairness state advances only
    when the enclosing work commits.
    """
    if not assign_to:
        return RoutingResult(user_id=None, email=None)

    # Explicit-email path: developer handed us the address directly.
    explicit_email = assign_to.get("email")
    if explicit_email:
        user = await _get_by_email(session, explicit_email)
        if user is None:
            # Trust the developer — we'll route to the literal address.
            # The task's `assigned_to_user_id` stays null; routing works
            # via `assigned_to_email`. An operator seeing the row can
            # add the user later if they want the fairness tracking.
            return RoutingResult(user_id=None, email=explicit_email)
        return _result_from_user(user)

    # Marketplace path — out of scope for v1, pass through so nothing
    # routes to a non-existent user.
    if "marketplace" in assign_to:
        return RoutingResult(user_id=None, email=None)

    # Role/filter-based routing — pick the least-recently-assigned
    # active user matching the filters.
    role = assign_to.get("role")
    access_level = assign_to.get("access_level")
    pool = assign_to.get("pool")

    if not any([role, access_level, pool]):
        # No filters and no email — caller asked for nothing routable.
        return RoutingResult(user_id=None, email=None)

    picked = await _pick_least_recently_assigned(
        session, role=role, access_level=access_level, pool=pool
    )
    if picked is None:
        logger.info(
            "No user matched routing filters role=%r access_level=%r pool=%r",
            role, access_level, pool,
        )
        return RoutingResult(user_id=None, email=None)

    picked.last_assigned_at = datetime.now(timezone.utc)
    session.add(picked)

    return _result_from_user(picked)


async def _get_by_email(session: AsyncSession, email: str) -> User | None:
    result = await session.execute(select(User).where(User.email == email))
    return result.scalar_one_or_none()


async def _pick_least_recently_assigned(
    session: AsyncSession,
    *,
    role: str | None,
    access_level: str | None,
    pool: str | None,
) -> User | None:
    """Pick the active user with the oldest `last_assigned_at`.

    Null sorts first (SQLite's default is NULLS FIRST for ASC; Postgres
    defaults to NULLS LAST, so we pin it explicitly). Fresh hires never
    get picked last by accident on Postgres.

    On Postgres we could add `FOR UPDATE SKIP LOCKED` to serialize
    pickers and get stronger fairness under concurrency. Not needed on
    SQLite (single-writer). Deferred to post-launch — v1 accepts that
    two concurrent pickers may land on the same user, the next task
    then picks someone else as the timestamp has been bumped.
    """
    stmt = (
        select(User)
        .where(User.active == True)  # noqa: E712 — SQLAlchemy idiom
        .order_by(User.last_assigned_at.asc().nulls_first(), User.created_at.asc())
        .limit(1)
    )
    if role is not None:
        stmt = stmt.where(User.role == role)
    if access_level is not None:
        stmt = stmt.where(User.access_level == access_level)
    if pool is not None:
        stmt = stmt.where(User.pool == pool)

    result = await session.execute(stmt)
    return result.scalar_one_or_none()


def _result_from_user(user: User) -> RoutingResult:
    return RoutingResult(
        user_id=user.id,
        email=user.email,
        slack_team_id=user.slack_team_id,
        slack_user_id=user.slack_user_id,
    )
