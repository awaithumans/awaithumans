"""First-run /setup bootstrap — token flow + one-shot semantics."""

from __future__ import annotations

from collections.abc import AsyncGenerator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from awaithumans.server.app import create_app
from awaithumans.server.core import bootstrap
from awaithumans.utils.constants import DASHBOARD_SESSION_COOKIE_NAME


@pytest_asyncio.fixture
async def blank_client() -> AsyncGenerator[AsyncClient, None]:
    """App with a fresh empty DB — no operator seeded.

    `_isolated_db` + `_payload_key` autouse fixtures from conftest.py
    handle DB + crypto setup.
    """
    app = create_app(serve_dashboard=False)
    async with app.router.lifespan_context(app):
        transport = ASGITransport(app=app)
        async with AsyncClient(
            transport=transport, base_url="http://testserver", follow_redirects=False
        ) as c:
            yield c


@pytest.mark.asyncio
async def test_status_reports_needs_setup_on_empty_db(
    blank_client: AsyncClient,
) -> None:
    resp = await blank_client.get("/api/setup/status")
    assert resp.status_code == 200
    body = resp.json()
    assert body["needs_setup"] is True
    assert body["token_active"] is True


@pytest.mark.asyncio
async def test_status_reports_complete_once_user_exists(
    blank_client: AsyncClient,
) -> None:
    """Bootstrap a user via the /setup flow itself, then re-check
    status — should flip to needs_setup=false."""
    token = bootstrap.ensure_token()
    r = await blank_client.post(
        "/api/setup/operator",
        json={
            "token": token,
            "email": "op@example.com",
            "password": "hunter2a",
            "display_name": "Op",
        },
    )
    assert r.status_code == 201

    resp = await blank_client.get("/api/setup/status")
    assert resp.json()["needs_setup"] is False


@pytest.mark.asyncio
async def test_create_first_operator_requires_token(
    blank_client: AsyncClient,
) -> None:
    bootstrap.ensure_token()  # active token in memory
    resp = await blank_client.post(
        "/api/setup/operator",
        json={
            "token": "definitely-not-the-right-token",
            "email": "op@example.com",
            "password": "hunter2a",
        },
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_create_first_operator_issues_session(
    blank_client: AsyncClient,
) -> None:
    """Successful bootstrap logs the operator in immediately — no
    redundant login step."""
    token = bootstrap.ensure_token()
    resp = await blank_client.post(
        "/api/setup/operator",
        json={
            "token": token,
            "email": "op@example.com",
            "password": "hunter2a",
        },
    )
    assert resp.status_code == 201
    assert DASHBOARD_SESSION_COOKIE_NAME in resp.cookies


@pytest.mark.asyncio
async def test_second_bootstrap_attempt_409s(blank_client: AsyncClient) -> None:
    """One-shot: after the first operator exists, the endpoint 409s
    regardless of whether the caller still has a valid token."""
    token = bootstrap.ensure_token()
    r1 = await blank_client.post(
        "/api/setup/operator",
        json={"token": token, "email": "op1@example.com", "password": "hunter2a"},
    )
    assert r1.status_code == 201

    r2 = await blank_client.post(
        "/api/setup/operator",
        json={"token": token, "email": "op2@example.com", "password": "hunter2b"},
    )
    assert r2.status_code == 409


@pytest.mark.asyncio
async def test_setup_routes_bypass_auth_middleware(
    blank_client: AsyncClient,
) -> None:
    """No session cookie, no admin token → still reaches /setup/*
    (that's the whole point — it's the bootstrap)."""
    resp = await blank_client.get("/api/setup/status")
    assert resp.status_code == 200


def test_bootstrap_module_is_idempotent() -> None:
    """`ensure_token` called twice returns the same token until
    `mark_complete` runs."""
    import awaithumans.server.core.bootstrap as b

    b._token = None
    b._completed = False
    t1 = b.ensure_token()
    t2 = b.ensure_token()
    assert t1 == t2

    b.mark_complete()
    assert not b.is_active()


def test_bootstrap_verify_rejects_after_complete() -> None:
    import awaithumans.server.core.bootstrap as b

    b._token = None
    b._completed = False
    t = b.ensure_token()
    assert b.verify_token(t) is True
    b.mark_complete()
    assert b.verify_token(t) is False
