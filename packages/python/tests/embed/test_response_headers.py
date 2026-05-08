"""Integration tests for /embed/* response-header bundle and auth-skip (Task 14).

Inline fixtures — no dependency on Task 15 conftest.

Exercises:
  1. GET /embed/anything returns Content-Security-Policy with frame-ancestors,
     frame-src 'none', default-src 'self', and connect-src 'self'.
  2. GET /embed/anything returns Referrer-Policy: no-referrer.
  3. GET /embed/anything returns Permissions-Policy with geolocation=(),
     microphone=(), camera=().
  4. Anonymous GET /embed/... does NOT 302 to /login (auth skip).
"""

from __future__ import annotations

import asyncio
from collections.abc import Iterator

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlmodel import SQLModel

from awaithumans.server.core.auth import DashboardAuthMiddleware
from awaithumans.server.core.config import settings
from awaithumans.server.core.embed_auth import EmbedAuthMiddleware
from awaithumans.server.core.exceptions import exception_handlers
from awaithumans.server.db.connection import get_session

# ── Constants ─────────────────────────────────────────────────────────────────

_SIGNING_SECRET = "x" * 32
_ALLOWED_ORIGIN = "https://acme.com"


# ── In-memory async engine ────────────────────────────────────────────────────


def _make_engine():
    return create_async_engine("sqlite+aiosqlite:///:memory:")


async def _setup_db(engine) -> None:
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)


def _build_app(engine) -> FastAPI:
    """Build a minimal app with DashboardAuthMiddleware + EmbedAuthMiddleware
    (mirrors the real app stack) and EmbedResponseHeadersMiddleware."""
    from awaithumans.server.app import EmbedResponseHeadersMiddleware

    asyncio.new_event_loop().run_until_complete(_setup_db(engine))

    test_factory = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async def _override_get_session():
        async with test_factory() as session:
            yield session

    app = FastAPI()
    for exc_class, handler in exception_handlers.items():
        app.add_exception_handler(exc_class, handler)

    # Replicate the real middleware stack order from app.py.
    # Last-added = first-executed in Starlette's middleware chain.
    app.add_middleware(DashboardAuthMiddleware)
    app.add_middleware(
        EmbedAuthMiddleware,
        secret_provider=lambda: settings.EMBED_SIGNING_SECRET,
    )
    app.add_middleware(EmbedResponseHeadersMiddleware)
    app.dependency_overrides[get_session] = _override_get_session

    return app


# ── Module-level fixtures ─────────────────────────────────────────────────────


@pytest.fixture(autouse=True)
def _embed_settings() -> Iterator[None]:
    """Patch embed settings for the duration of each test."""
    original_secret = settings.EMBED_SIGNING_SECRET
    original_origins = settings.EMBED_PARENT_ORIGINS

    settings.EMBED_SIGNING_SECRET = _SIGNING_SECRET
    settings.EMBED_PARENT_ORIGINS = _ALLOWED_ORIGIN

    yield

    settings.EMBED_SIGNING_SECRET = original_secret
    settings.EMBED_PARENT_ORIGINS = original_origins


@pytest.fixture
def client() -> Iterator[TestClient]:
    """Yield a TestClient backed by a fresh in-memory DB."""
    engine = _make_engine()
    app = _build_app(engine)
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c
    asyncio.new_event_loop().run_until_complete(engine.dispose())


# ── Tests ─────────────────────────────────────────────────────────────────────


def test_embed_path_has_csp_header(client: TestClient) -> None:
    """GET /embed/anything returns a Content-Security-Policy header."""
    resp = client.get("/embed/anything", follow_redirects=False)
    csp = resp.headers.get("content-security-policy", "")
    assert "frame-ancestors" in csp, f"Expected frame-ancestors in CSP, got: {csp!r}"
    assert "frame-src 'none'" in csp, f"Expected frame-src 'none' in CSP, got: {csp!r}"
    assert "default-src 'self'" in csp, f"Expected default-src 'self' in CSP, got: {csp!r}"
    assert "connect-src 'self'" in csp, f"Expected connect-src 'self' in CSP, got: {csp!r}"


def test_embed_path_has_referrer_policy(client: TestClient) -> None:
    """GET /embed/anything returns Referrer-Policy: no-referrer."""
    resp = client.get("/embed/anything", follow_redirects=False)
    assert resp.headers.get("referrer-policy") == "no-referrer"


def test_embed_path_has_permissions_policy(client: TestClient) -> None:
    """GET /embed/anything returns Permissions-Policy with restrictive values."""
    resp = client.get("/embed/anything", follow_redirects=False)
    pp = resp.headers.get("permissions-policy", "")
    assert "geolocation=()" in pp, f"Expected geolocation=() in Permissions-Policy, got: {pp!r}"
    assert "microphone=()" in pp, f"Expected microphone=() in Permissions-Policy, got: {pp!r}"
    assert "camera=()" in pp, f"Expected camera=() in Permissions-Policy, got: {pp!r}"


def test_anonymous_embed_request_does_not_redirect_to_login(client: TestClient) -> None:
    """Anonymous GET /embed/... must NOT 302 to /login (auth skip in DashboardAuthMiddleware)."""
    resp = client.get("/embed/anything", follow_redirects=False)
    is_login_redirect = resp.status_code == 302 and "login" in resp.headers.get("location", "")
    assert not is_login_redirect, (
        f"Expected no redirect to /login, got {resp.status_code} "
        f"location={resp.headers.get('location')!r}"
    )
