"""Auth routes + DashboardAuthMiddleware — live HTTP through FastAPI TestClient."""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from awaithumans.server.app import create_app
from awaithumans.utils.constants import DASHBOARD_SESSION_COOKIE_NAME


@pytest.fixture
def client(auth_enabled) -> Iterator[TestClient]:
    app = create_app(serve_dashboard=False)
    with TestClient(app) as c:
        yield c


@pytest.fixture
def no_auth_client(auth_disabled) -> Iterator[TestClient]:
    app = create_app(serve_dashboard=False)
    with TestClient(app) as c:
        yield c


# ─── /api/auth/me ───────────────────────────────────────────────────────


def test_me_when_auth_disabled(no_auth_client: TestClient) -> None:
    resp = no_auth_client.get("/api/auth/me")
    assert resp.status_code == 200
    data = resp.json()
    assert data == {"authenticated": False, "user": None, "auth_enabled": False}


def test_me_when_auth_enabled_but_not_logged_in(client: TestClient) -> None:
    resp = client.get("/api/auth/me")
    assert resp.status_code == 200
    data = resp.json()
    assert data["auth_enabled"] is True
    assert data["authenticated"] is False


# ─── /api/auth/login ────────────────────────────────────────────────────


def test_login_success_sets_cookie(client: TestClient) -> None:
    resp = client.post(
        "/api/auth/login",
        json={"user": "admin", "password": "correct-horse-battery-staple"},
    )
    assert resp.status_code == 204
    assert DASHBOARD_SESSION_COOKIE_NAME in resp.cookies


def test_login_wrong_password_401(client: TestClient) -> None:
    resp = client.post(
        "/api/auth/login",
        json={"user": "admin", "password": "wrong"},
    )
    assert resp.status_code == 401
    assert DASHBOARD_SESSION_COOKIE_NAME not in resp.cookies


def test_login_wrong_user_401(client: TestClient) -> None:
    resp = client.post(
        "/api/auth/login",
        json={"user": "hacker", "password": "correct-horse-battery-staple"},
    )
    assert resp.status_code == 401


def test_login_when_auth_disabled_503(no_auth_client: TestClient) -> None:
    """Login makes no sense when no password is configured."""
    resp = no_auth_client.post(
        "/api/auth/login",
        json={"user": "admin", "password": "admin"},
    )
    assert resp.status_code == 503


# ─── /api/auth/logout ───────────────────────────────────────────────────


def test_logout_clears_cookie(client: TestClient) -> None:
    # First log in.
    login = client.post(
        "/api/auth/login",
        json={"user": "admin", "password": "correct-horse-battery-staple"},
    )
    assert login.status_code == 204

    resp = client.post("/api/auth/logout")
    assert resp.status_code == 204
    # Server sets a zero-age cookie to expire it — TestClient clears it.
    # Verify /me now reports unauthenticated.
    me = client.get("/api/auth/me")
    assert me.status_code == 200
    assert me.json()["authenticated"] is False


# ─── Middleware gate ────────────────────────────────────────────────────


def test_protected_route_without_session_401(client: TestClient) -> None:
    resp = client.get("/api/tasks")
    assert resp.status_code == 401


def test_protected_route_with_session_200(client: TestClient) -> None:
    login = client.post(
        "/api/auth/login",
        json={"user": "admin", "password": "correct-horse-battery-staple"},
    )
    assert login.status_code == 204
    resp = client.get("/api/tasks")
    assert resp.status_code == 200  # empty list, but reachable


def test_protected_route_with_bogus_cookie_401(client: TestClient) -> None:
    client.cookies.set(DASHBOARD_SESSION_COOKIE_NAME, "not-a-real-token")
    resp = client.get("/api/tasks")
    assert resp.status_code == 401


def test_health_is_public_even_when_auth_on(client: TestClient) -> None:
    resp = client.get("/api/health")
    assert resp.status_code == 200


def test_auth_routes_reachable_without_cookie(client: TestClient) -> None:
    """Login endpoint can't require a cookie — it's the bootstrap."""
    resp = client.get("/api/auth/me")
    assert resp.status_code == 200


def test_admin_token_bypasses_session(client: TestClient, monkeypatch) -> None:
    """Bearer ADMIN_API_TOKEN is the ops skeleton key — no session needed."""
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


def test_no_auth_mode_lets_everything_through(no_auth_client: TestClient) -> None:
    """When DASHBOARD_PASSWORD is unset the middleware is a no-op."""
    resp = no_auth_client.get("/api/tasks")
    assert resp.status_code == 200
