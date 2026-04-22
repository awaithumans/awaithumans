"""Auth routes + DashboardAuthMiddleware — DB-backed login via real TestClient."""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from awaithumans.server.app import create_app
from awaithumans.server.db.models import User
from awaithumans.utils.constants import DASHBOARD_SESSION_COOKIE_NAME

from .conftest import OPERATOR_EMAIL, OPERATOR_PASSWORD


@pytest.fixture
def client(operator_user: User) -> Iterator[TestClient]:
    """App + DB migrations + seeded operator — ready to log in against."""
    app = create_app(serve_dashboard=False)
    with TestClient(app) as c:
        yield c


# ─── /api/auth/me ───────────────────────────────────────────────────────


def test_me_when_not_logged_in(client: TestClient) -> None:
    resp = client.get("/api/auth/me")
    assert resp.status_code == 200
    body = resp.json()
    assert body["authenticated"] is False


def test_me_after_login_returns_user(client: TestClient, operator_user: User) -> None:
    login = client.post(
        "/api/auth/login",
        json={"email": OPERATOR_EMAIL, "password": OPERATOR_PASSWORD},
    )
    assert login.status_code == 204

    resp = client.get("/api/auth/me")
    assert resp.status_code == 200
    body = resp.json()
    assert body["authenticated"] is True
    assert body["email"] == OPERATOR_EMAIL
    assert body["user_id"] == operator_user.id
    assert body["is_operator"] is True


# ─── /api/auth/login ────────────────────────────────────────────────────


def test_login_success_sets_cookie(client: TestClient) -> None:
    resp = client.post(
        "/api/auth/login",
        json={"email": OPERATOR_EMAIL, "password": OPERATOR_PASSWORD},
    )
    assert resp.status_code == 204
    assert DASHBOARD_SESSION_COOKIE_NAME in resp.cookies


def test_login_wrong_password_401(client: TestClient) -> None:
    resp = client.post(
        "/api/auth/login",
        json={"email": OPERATOR_EMAIL, "password": "wrong"},
    )
    assert resp.status_code == 401
    assert DASHBOARD_SESSION_COOKIE_NAME not in resp.cookies


def test_login_unknown_email_401(client: TestClient) -> None:
    resp = client.post(
        "/api/auth/login",
        json={"email": "nobody@example.com", "password": OPERATOR_PASSWORD},
    )
    assert resp.status_code == 401


# ─── /api/auth/logout ───────────────────────────────────────────────────


def test_logout_clears_cookie(client: TestClient) -> None:
    client.post(
        "/api/auth/login",
        json={"email": OPERATOR_EMAIL, "password": OPERATOR_PASSWORD},
    )
    resp = client.post("/api/auth/logout")
    assert resp.status_code == 204

    me = client.get("/api/auth/me")
    assert me.json()["authenticated"] is False


# ─── Middleware gate ────────────────────────────────────────────────────


def test_protected_route_without_session_401(client: TestClient) -> None:
    resp = client.get("/api/tasks")
    assert resp.status_code == 401


def test_protected_route_with_session_200(client: TestClient) -> None:
    login = client.post(
        "/api/auth/login",
        json={"email": OPERATOR_EMAIL, "password": OPERATOR_PASSWORD},
    )
    assert login.status_code == 204
    resp = client.get("/api/tasks")
    assert resp.status_code == 200  # empty list, but reachable


def test_protected_route_with_bogus_cookie_401(client: TestClient) -> None:
    client.cookies.set(DASHBOARD_SESSION_COOKIE_NAME, "not-a-real-token")
    resp = client.get("/api/tasks")
    assert resp.status_code == 401


def test_health_is_public(client: TestClient) -> None:
    resp = client.get("/api/health")
    assert resp.status_code == 200


def test_setup_routes_are_public(client: TestClient) -> None:
    """Even with a user in the DB, /api/setup/* routes skip the auth
    middleware — they gate themselves."""
    resp = client.get("/api/setup/status")
    assert resp.status_code == 200
    # With a user already present, setup is no longer needed.
    assert resp.json()["needs_setup"] is False


def test_admin_token_bypasses_session(client: TestClient, monkeypatch) -> None:
    """Bearer ADMIN_API_TOKEN is the automation escape hatch."""
    from awaithumans.server.core.config import settings

    monkeypatch.setattr(settings, "ADMIN_API_TOKEN", "top-secret-ops-token")
    resp = client.get(
        "/api/tasks",
        headers={"Authorization": "Bearer top-secret-ops-token"},
    )
    assert resp.status_code == 200


def test_admin_token_wrong_value_401(client: TestClient, monkeypatch) -> None:
    from awaithumans.server.core.config import settings

    monkeypatch.setattr(settings, "ADMIN_API_TOKEN", "top-secret-ops-token")
    resp = client.get(
        "/api/tasks",
        headers={"Authorization": "Bearer nope"},
    )
    assert resp.status_code == 401


def test_inactive_user_cannot_login(client: TestClient, monkeypatch) -> None:
    """Deactivating a user blocks new logins (existing sessions keep
    working until expiry — tradeoff for no DB hit per request).

    Uses a non-operator user since the last-active-operator guard
    (post-security-audit) refuses to deactivate the only operator.
    """
    import asyncio

    from awaithumans.server.db.connection import get_async_session_factory
    from awaithumans.server.services.user_service import create_user, update_user

    factory = get_async_session_factory()
    other_email = "regular@example.com"
    other_password = "other-password-xyz"

    async def _seed_and_deactivate() -> None:
        async with factory() as session:
            u = await create_user(
                session,
                email=other_email,
                display_name="Regular user",
                password=other_password,
            )
            await update_user(session, u.id, active=False)

    asyncio.get_event_loop().run_until_complete(_seed_and_deactivate())

    resp = client.post(
        "/api/auth/login",
        json={"email": other_email, "password": other_password},
    )
    assert resp.status_code == 401
