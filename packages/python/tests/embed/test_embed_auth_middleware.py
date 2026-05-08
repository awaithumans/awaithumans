"""Tests for EmbedAuthMiddleware.

Covers:
  1. Valid bearer token → 200 with task_id set.
  2. No Authorization header → 200 with task_id None.
  3. Authorization: Basic ... → 200 with task_id None (non-bearer ignored).
  4. Authorization: Bearer not.a.jwt → 401 with error.code == "INVALID_EMBED_TOKEN".
"""

from __future__ import annotations

from fastapi import FastAPI, Request
from starlette.testclient import TestClient

from awaithumans.server.core.embed_auth import EmbedAuthMiddleware
from awaithumans.server.services.embed_token_service import sign_embed_token

SECRET = "x" * 32


def _make_app() -> FastAPI:
    app = FastAPI()
    app.add_middleware(EmbedAuthMiddleware, secret_provider=lambda: SECRET)

    @app.get("/probe")
    def probe(request: Request) -> dict:  # type: ignore[type-arg]
        ctx = getattr(request.state, "embed_ctx", None)
        return {"task_id": ctx.task_id if ctx else None}

    return app


# ── 1. Valid bearer token ─────────────────────────────────────────────────


def test_valid_bearer_sets_embed_ctx() -> None:
    """A valid embed JWT in the Authorization header sets embed_ctx on request.state."""
    token, _ = sign_embed_token(
        secret=SECRET,
        task_id="tsk_01",
        sub="acme:u1",
        kind="end_user",
        parent_origin="https://acme.com",
        ttl_seconds=300,
    )
    client = TestClient(_make_app())
    resp = client.get("/probe", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert resp.json() == {"task_id": "tsk_01"}


# ── 2. No Authorization header ────────────────────────────────────────────


def test_no_auth_header_passes_through_anonymous() -> None:
    """Requests with no Authorization header pass through with embed_ctx = None."""
    client = TestClient(_make_app())
    resp = client.get("/probe")
    assert resp.status_code == 200
    assert resp.json() == {"task_id": None}


# ── 3. Non-bearer Authorization scheme ───────────────────────────────────


def test_basic_auth_header_passes_through_anonymous() -> None:
    """Authorization: Basic ... is ignored; embed_ctx is set to None."""
    client = TestClient(_make_app())
    resp = client.get("/probe", headers={"Authorization": "Basic dXNlcjpwYXNz"})
    assert resp.status_code == 200
    assert resp.json() == {"task_id": None}


# ── 4. Invalid JWT → 401 ─────────────────────────────────────────────────


def test_invalid_bearer_token_returns_401() -> None:
    """A Bearer token that is not a valid JWT returns 401 with INVALID_EMBED_TOKEN."""
    client = TestClient(_make_app())
    resp = client.get("/probe", headers={"Authorization": "Bearer not.a.jwt"})
    assert resp.status_code == 401
    body = resp.json()
    assert body["error"]["code"] == "INVALID_EMBED_TOKEN"
