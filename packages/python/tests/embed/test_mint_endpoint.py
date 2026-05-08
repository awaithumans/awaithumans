"""Integration tests for POST /api/embed/tokens (mint endpoint).

Inline fixtures — no dependency on Task 15 conftest. Task 15 will later
replace these with shared fixtures.

Approach: build a minimal FastAPI app with just the embed router + centralized
exception handlers, wired to an in-memory aiosqlite DB. Avoids the full
create_app() startup (PAYLOAD_KEY guard, Alembic migrations, lifespan, etc.)
while still exercising the real route code.
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

from awaithumans.server.core.config import settings
from awaithumans.server.core.exceptions import exception_handlers
from awaithumans.server.db.connection import get_session
from awaithumans.server.db.models import Task
from awaithumans.server.db.models.base import utc_now
from awaithumans.server.routes import embed as embed_routes
from awaithumans.server.services.service_key_service import create_service_key
from awaithumans.types import TaskStatus

# ── Constants ────────────────────────────────────────────────────────────────

_SIGNING_SECRET = "x" * 32
_ALLOWED_ORIGIN = "https://acme.com"
_TASK_ID = "tsk_seeded"


# ── In-memory async engine + session override ────────────────────────────────


def _make_engine():
    return create_async_engine("sqlite+aiosqlite:///:memory:")


async def _setup_db(engine):
    """Create all tables and seed one Task + one ServiceAPIKey. Return raw key."""
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)

    factory = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as session:
        # Seed a task
        task = Task(
            id=_TASK_ID,
            idempotency_key="idem-seeded",
            task="Review this document",
            payload={},
            payload_schema={},
            response_schema={},
            timeout_seconds=3600,
            status=TaskStatus.CREATED,
            created_at=utc_now(),
            updated_at=utc_now(),
        )
        session.add(task)
        await session.flush()

        # Seed a service key
        raw_key, _ = await create_service_key(session, name="test-key")
        await session.commit()

    return raw_key


def _build_app(engine) -> tuple[FastAPI, str]:
    """Build a minimal app wired to the given engine. Returns (app, raw_key)."""
    raw_key = asyncio.new_event_loop().run_until_complete(_setup_db(engine))

    test_factory = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async def _override_get_session():
        async with test_factory() as session:
            yield session

    app = FastAPI()
    for exc_class, handler in exception_handlers.items():
        app.add_exception_handler(exc_class, handler)
    app.include_router(embed_routes.router)
    app.dependency_overrides[get_session] = _override_get_session

    return app, raw_key


# ── Module-level fixtures ─────────────────────────────────────────────────────


@pytest.fixture(autouse=True)
def _embed_settings() -> Iterator[None]:
    """Set required embed env vars on the settings singleton for the duration
    of each test, then restore originals."""
    original_secret = settings.EMBED_SIGNING_SECRET
    original_origins = settings.EMBED_PARENT_ORIGINS
    original_svc_key = settings.SERVICE_API_KEY

    settings.EMBED_SIGNING_SECRET = _SIGNING_SECRET
    settings.EMBED_PARENT_ORIGINS = _ALLOWED_ORIGIN
    settings.SERVICE_API_KEY = None  # force DB-backed key verification by default

    yield

    settings.EMBED_SIGNING_SECRET = original_secret
    settings.EMBED_PARENT_ORIGINS = original_origins
    settings.SERVICE_API_KEY = original_svc_key


@pytest.fixture
def client_and_key() -> Iterator[tuple[TestClient, str]]:
    """Yield (TestClient, raw_service_key) backed by a fresh in-memory DB."""
    engine = _make_engine()
    app, raw_key = _build_app(engine)
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c, raw_key
    asyncio.new_event_loop().run_until_complete(engine.dispose())


# ── Tests ─────────────────────────────────────────────────────────────────────


def test_unauthenticated_returns_401(client_and_key: tuple[TestClient, str]) -> None:
    """POST without Authorization header → 401."""
    client, _ = client_and_key
    resp = client.post(
        "/api/embed/tokens",
        json={
            "task_id": _TASK_ID,
            "parent_origin": _ALLOWED_ORIGIN,
        },
    )
    assert resp.status_code == 401


def test_valid_request_returns_token(client_and_key: tuple[TestClient, str]) -> None:
    """Valid request → 200 with embed_token, embed_url, expires_at."""
    client, raw_key = client_and_key
    resp = client.post(
        "/api/embed/tokens",
        json={
            "task_id": _TASK_ID,
            "parent_origin": _ALLOWED_ORIGIN,
        },
        headers={"Authorization": f"Bearer {raw_key}"},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert "embed_token" in body
    assert "embed_url" in body
    assert "expires_at" in body
    token = body["embed_token"]
    assert body["embed_url"].endswith(f"#token={token}")


def test_disallowed_origin_returns_400(client_and_key: tuple[TestClient, str]) -> None:
    """parent_origin not in allowlist → 400 / EMBED_ORIGIN_NOT_ALLOWED."""
    client, raw_key = client_and_key
    resp = client.post(
        "/api/embed/tokens",
        json={
            "task_id": _TASK_ID,
            "parent_origin": "https://evil.com",
        },
        headers={"Authorization": f"Bearer {raw_key}"},
    )
    assert resp.status_code == 400
    body = resp.json()
    assert body["error"] == "EMBED_ORIGIN_NOT_ALLOWED"


def test_unknown_task_id_returns_404(client_and_key: tuple[TestClient, str]) -> None:
    """Unknown task_id → 404."""
    client, raw_key = client_and_key
    resp = client.post(
        "/api/embed/tokens",
        json={
            "task_id": "tsk_does_not_exist",
            "parent_origin": _ALLOWED_ORIGIN,
        },
        headers={"Authorization": f"Bearer {raw_key}"},
    )
    assert resp.status_code == 404


def test_large_ttl_clamps_without_error(client_and_key: tuple[TestClient, str]) -> None:
    """ttl_seconds: 999999 clamps successfully — no 4xx/5xx."""
    client, raw_key = client_and_key
    resp = client.post(
        "/api/embed/tokens",
        json={
            "task_id": _TASK_ID,
            "parent_origin": _ALLOWED_ORIGIN,
            "ttl_seconds": 999999,
        },
        headers={"Authorization": f"Bearer {raw_key}"},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert "embed_token" in body
