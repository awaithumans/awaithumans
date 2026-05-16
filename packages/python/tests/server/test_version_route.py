"""GET /api/version — server's running package version, public.

Used by ops monitoring and by SDKs that want to surface "you're
behind the server" hints before authenticating.
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
    encryption both derive from it). Set a per-test value."""
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


def test_returns_package_version(client: TestClient) -> None:
    resp = client.get("/api/version")
    assert resp.status_code == 200
    payload = resp.json()
    assert payload == {"name": "awaithumans", "version": __version__}


def test_does_not_require_auth(client: TestClient) -> None:
    """Ops tooling and pre-auth SDK probes need to read this without
    presenting credentials. If the auth bypass entry in core/auth.py
    is missing, this would 401 instead of 200."""
    resp = client.get("/api/version")
    assert resp.status_code == 200, (
        "GET /api/version must be reachable without a session — check "
        "_PUBLIC_PREFIXES in core/auth.py."
    )


def test_content_type_is_json(client: TestClient) -> None:
    """Don't let the dashboard's static-file fallback catch this with
    its own HTML 404 — that would silently regress the contract."""
    resp = client.get("/api/version")
    assert resp.headers["content-type"].startswith("application/json")
