"""Per-task authorization at the HTTP layer.

These tests exercise `/api/tasks/*` routes through real HTTP, asserting
the auth gates added in PR-sec-1:

  - admin bearer: full access (agent / ops scripts)
  - operator session: full access
  - non-operator session: scoped to their own assigned tasks; cannot
    read or complete other people's tasks; cannot create / cancel /
    audit anything

Without these gates, any logged-in user could enumerate every task,
read full payloads + responses, complete tasks they were never
assigned to, and uninstall Slack workspaces. The reviews surfaced
this as the launch-blocking authorisation gap; tests below pin the
fix so a regression can't slip past CI.
"""

from __future__ import annotations

import asyncio
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from awaithumans.server.app import create_app
from awaithumans.server.core.config import settings
from awaithumans.server.db.models import User

from tests.auth.conftest import OPERATOR_PASSWORD

REVIEWER_EMAIL = "reviewer@example.com"
REVIEWER_PASSWORD = "reviewer-correct-horse-battery"
OTHER_USER_EMAIL = "other@example.com"


@pytest.fixture
def client(operator_user: User) -> Iterator[TestClient]:
    app = create_app(serve_dashboard=False)
    with TestClient(app) as c:
        yield c


@pytest.fixture
def reviewer_user(operator_user: User) -> User:
    """Seed a non-operator reviewer alongside the operator. Used to
    assert non-operators get scoped task visibility and 403s on
    operator-only routes."""
    from awaithumans.server.db.connection import get_async_session_factory
    from awaithumans.server.services.user_service import create_user

    async def _seed() -> User:
        factory = get_async_session_factory()
        async with factory() as session:
            return await create_user(
                session,
                email=REVIEWER_EMAIL,
                display_name="Reviewer",
                is_operator=False,
                password=REVIEWER_PASSWORD,
            )

    return asyncio.new_event_loop().run_until_complete(_seed())


@pytest.fixture
def other_user(operator_user: User) -> User:
    """A second non-operator — used as the assignee on tasks the
    reviewer should NOT be able to see."""
    from awaithumans.server.db.connection import get_async_session_factory
    from awaithumans.server.services.user_service import create_user

    async def _seed() -> User:
        factory = get_async_session_factory()
        async with factory() as session:
            return await create_user(
                session,
                email=OTHER_USER_EMAIL,
                display_name="Other",
                is_operator=False,
            )

    return asyncio.new_event_loop().run_until_complete(_seed())


def _admin_headers() -> dict[str, str]:
    settings.ADMIN_API_TOKEN = "test-admin-token"
    return {"Authorization": f"Bearer {settings.ADMIN_API_TOKEN}"}


def _login(client: TestClient, email: str, password: str) -> None:
    resp = client.post(
        "/api/auth/login", json={"email": email, "password": password}
    )
    assert resp.status_code == 204, resp.text


def _make_task(
    client: TestClient,
    *,
    assigned_to_email: str | None = None,
    idempotency_key: str = "task-1",
) -> str:
    body: dict = {
        "task": "Approve refund",
        "payload": {"amount": 100},
        "payload_schema": {"type": "object"},
        "response_schema": {"type": "object"},
        "timeout_seconds": 900,
        "idempotency_key": idempotency_key,
    }
    if assigned_to_email is not None:
        body["assign_to"] = {"email": assigned_to_email}
    resp = client.post("/api/tasks", json=body, headers=_admin_headers())
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


# ─── Create / cancel / audit are operator-or-admin only ──────────────────


def test_create_task_blocked_for_non_operator(
    client: TestClient, reviewer_user: User
) -> None:
    """Non-operator session must NOT be able to create tasks. The agent
    is the canonical caller (admin bearer); allowing reviewers to
    create tasks would let them bypass the verifier-config and routing
    decisions baked into agent code."""
    _login(client, REVIEWER_EMAIL, REVIEWER_PASSWORD)
    resp = client.post(
        "/api/tasks",
        json={
            "task": "x",
            "payload": {},
            "payload_schema": {},
            "response_schema": {},
            "timeout_seconds": 900,
            "idempotency_key": "no",
        },
    )
    assert resp.status_code == 403


def test_cancel_blocked_for_non_operator(
    client: TestClient, reviewer_user: User, other_user: User
) -> None:
    """Even the assignee shouldn't be able to cancel — the agent
    expects to see the task through to completion or timeout."""
    task_id = _make_task(client, assigned_to_email=REVIEWER_EMAIL)
    _login(client, REVIEWER_EMAIL, REVIEWER_PASSWORD)
    resp = client.post(f"/api/tasks/{task_id}/cancel")
    assert resp.status_code == 403


def test_audit_blocked_for_non_operator(
    client: TestClient, reviewer_user: User
) -> None:
    """Audit can quote response keys + completer emails + verifier
    reasoning; not for non-operator eyes."""
    task_id = _make_task(client, assigned_to_email=REVIEWER_EMAIL)
    _login(client, REVIEWER_EMAIL, REVIEWER_PASSWORD)
    resp = client.get(f"/api/tasks/{task_id}/audit")
    assert resp.status_code == 403


# ─── List is scoped to assignee for non-operators ────────────────────────


def test_list_scoped_to_assignee_for_non_operator(
    client: TestClient, reviewer_user: User, other_user: User
) -> None:
    """A reviewer logged into the dashboard must only see tasks routed
    to them — not the operator's, not other reviewers'."""
    mine = _make_task(
        client, assigned_to_email=REVIEWER_EMAIL, idempotency_key="mine"
    )
    _theirs = _make_task(
        client, assigned_to_email=OTHER_USER_EMAIL, idempotency_key="theirs"
    )

    _login(client, REVIEWER_EMAIL, REVIEWER_PASSWORD)
    resp = client.get("/api/tasks")
    assert resp.status_code == 200
    ids = [t["id"] for t in resp.json()]
    assert mine in ids
    assert _theirs not in ids


def test_list_unscoped_for_operator(
    client: TestClient, reviewer_user: User
) -> None:
    """Operators see every task regardless of assignee."""
    a = _make_task(client, assigned_to_email=REVIEWER_EMAIL, idempotency_key="a")
    b = _make_task(
        client, assigned_to_email=OTHER_USER_EMAIL, idempotency_key="b"
    )
    _login(client, "operator@example.com", OPERATOR_PASSWORD)
    resp = client.get("/api/tasks")
    assert resp.status_code == 200
    ids = [t["id"] for t in resp.json()]
    assert a in ids
    assert b in ids


def test_list_assigned_to_filter_ignored_for_non_operator(
    client: TestClient, reviewer_user: User, other_user: User
) -> None:
    """A reviewer can't pass `assigned_to=other@example.com` to read
    someone else's tasks — server forces the filter to their own ID."""
    mine = _make_task(
        client, assigned_to_email=REVIEWER_EMAIL, idempotency_key="m"
    )
    _theirs = _make_task(
        client, assigned_to_email=OTHER_USER_EMAIL, idempotency_key="t"
    )
    _login(client, REVIEWER_EMAIL, REVIEWER_PASSWORD)
    resp = client.get(f"/api/tasks?assigned_to={OTHER_USER_EMAIL}")
    assert resp.status_code == 200
    ids = [t["id"] for t in resp.json()]
    assert _theirs not in ids
    assert ids == [mine] or ids == []


# ─── Get / complete enforce assignee match for non-operators ─────────────


def test_get_other_users_task_403_for_non_operator(
    client: TestClient, reviewer_user: User
) -> None:
    """Direct ID lookup must also gate — the reviewer might know a
    task ID from a stale Slack message."""
    task_id = _make_task(
        client, assigned_to_email=OTHER_USER_EMAIL, idempotency_key="g"
    )
    _login(client, REVIEWER_EMAIL, REVIEWER_PASSWORD)
    resp = client.get(f"/api/tasks/{task_id}")
    assert resp.status_code == 403


def test_get_own_task_succeeds_for_assignee(
    client: TestClient, reviewer_user: User
) -> None:
    task_id = _make_task(
        client, assigned_to_email=REVIEWER_EMAIL, idempotency_key="g2"
    )
    _login(client, REVIEWER_EMAIL, REVIEWER_PASSWORD)
    resp = client.get(f"/api/tasks/{task_id}")
    assert resp.status_code == 200
    assert resp.json()["id"] == task_id


def test_complete_other_users_task_403_for_non_operator(
    client: TestClient, reviewer_user: User
) -> None:
    """The most consequential gate: a non-operator must NOT complete a
    task assigned to someone else, even with a known task_id."""
    task_id = _make_task(
        client, assigned_to_email=OTHER_USER_EMAIL, idempotency_key="c"
    )
    _login(client, REVIEWER_EMAIL, REVIEWER_PASSWORD)
    resp = client.post(
        f"/api/tasks/{task_id}/complete",
        json={"response": {"approved": True}},
    )
    assert resp.status_code == 403


def test_complete_own_task_succeeds_for_assignee(
    client: TestClient, reviewer_user: User
) -> None:
    task_id = _make_task(
        client, assigned_to_email=REVIEWER_EMAIL, idempotency_key="c2"
    )
    _login(client, REVIEWER_EMAIL, REVIEWER_PASSWORD)
    resp = client.post(
        f"/api/tasks/{task_id}/complete",
        json={"response": {"approved": True}},
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "completed"
