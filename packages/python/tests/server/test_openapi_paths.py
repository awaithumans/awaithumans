"""OpenAPI/Swagger endpoints live under /api/* (per docs/api/overview.mdx).

The docs page promises:
  - /api/docs           — Swagger UI
  - /api/redoc          — ReDoc UI
  - /api/openapi.json   — raw OpenAPI 3 schema

Pre-fix, FastAPI's defaults left these at /docs, /redoc, /openapi.json —
inconsistent with the rest of the URL surface (every other backend
endpoint is under /api/...) and a copy-paste trap for anyone following
the docs.

These tests pin:
  - the documented paths return 200 without auth
  - the old root-level paths no longer expose Swagger
  - the FastAPI version field tracks `awaithumans.__version__`
"""

from __future__ import annotations

import secrets
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from awaithumans import __version__
from awaithumans.server.app import create_app
from awaithumans.server.core import encryption
from awaithumans.server.core.config import settings


@pytest.fixture(autouse=True)
def _payload_key() -> Iterator[None]:
    """`create_app` aborts boot without PAYLOAD_KEY (sessions + at-rest
    encryption both derive from it). Set a per-test value so the app
    factory succeeds."""
    original = settings.PAYLOAD_KEY
    settings.PAYLOAD_KEY = secrets.token_urlsafe(32)
    encryption.reset_key_cache()
    yield
    settings.PAYLOAD_KEY = original
    encryption.reset_key_cache()


@pytest.fixture
def client() -> Iterator[TestClient]:
    app = create_app(serve_dashboard=False)
    with TestClient(app) as c:
        yield c


def test_swagger_ui_served_at_api_docs(client: TestClient) -> None:
    """The path the docs page tells users to visit returns the Swagger UI."""
    resp = client.get("/api/docs")
    assert resp.status_code == 200
    assert "swagger-ui" in resp.text.lower()


def test_redoc_served_at_api_redoc(client: TestClient) -> None:
    resp = client.get("/api/redoc")
    assert resp.status_code == 200
    assert "redoc" in resp.text.lower()


def test_openapi_schema_served_at_api_openapi_json(client: TestClient) -> None:
    resp = client.get("/api/openapi.json")
    assert resp.status_code == 200
    schema = resp.json()
    assert schema["info"]["title"] == "awaithumans"
    assert schema["openapi"].startswith("3.")


def test_openapi_version_tracks_package_version(client: TestClient) -> None:
    """OpenAPI's `info.version` field is used by client codegen tools to
    label generated SDKs. Hardcoding `0.1.1` in the FastAPI constructor
    meant every codegen run after the 0.1.1 release labelled the SDK
    incorrectly. Now reads from `awaithumans.__version__` directly."""
    resp = client.get("/api/openapi.json")
    assert resp.json()["info"]["version"] == __version__


def test_old_root_docs_paths_no_longer_serve_swagger(
    client: TestClient,
) -> None:
    """Defensive: confirm we actually moved the routes, not just added
    new ones. A user who lands on the old /docs path should NOT get
    the Swagger UI from a stale registration."""
    for old_path in ("/docs", "/redoc", "/openapi.json"):
        resp = client.get(old_path)
        # Without the dashboard mounted (serve_dashboard=False), the old
        # paths now resolve through the auth middleware → 401 (no
        # session). What matters is "doesn't return Swagger HTML".
        assert "swagger-ui" not in resp.text.lower(), (
            f"{old_path} still appears to serve Swagger UI"
        )


def test_api_docs_does_not_require_auth(client: TestClient) -> None:
    """Public Swagger UI is the whole point of exposing it. Without the
    auth-middleware bypass entry, the docs would 401 for unauthenticated
    visitors — exactly the gap we just patched."""
    resp = client.get("/api/docs")
    assert resp.status_code == 200, (
        "Swagger UI must be reachable without a session cookie — check "
        "core/auth.py _PUBLIC_PREFIXES includes /api/docs."
    )


def test_api_openapi_json_does_not_require_auth(client: TestClient) -> None:
    resp = client.get("/api/openapi.json")
    assert resp.status_code == 200
