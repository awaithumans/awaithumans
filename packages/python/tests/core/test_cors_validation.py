"""CORS origin validation refuses unsafe configurations at boot.

The middleware in `app.py` flips `allow_credentials` ON the moment the
origin list isn't a bare `*`. Without validation, any operator who
sets a malformed origin list re-enables credential-bearing CORS to
whatever they typed — classic session-ride trap.

These tests pin the validator: starless `*`, plain http://, mixed
configs all refuse to start with an actionable error. The acceptable
shapes (bare `*`, https-only, http-localhost dev) are also pinned so
we don't regress them away."""

from __future__ import annotations

import pytest

from awaithumans.server.app import _validate_cors_origins


# ─── Acceptable configs ──────────────────────────────────────────────


def test_bare_wildcard_accepted() -> None:
    """`["*"]` alone is fine — credentials are forced off in this
    case so any origin can read public data without session cookies."""
    _validate_cors_origins(["*"])  # no raise


def test_https_origin_accepted() -> None:
    _validate_cors_origins(["https://app.acme.com"])


def test_https_origin_with_port_accepted() -> None:
    _validate_cors_origins(["https://app.acme.com:8443"])


def test_localhost_dev_accepted() -> None:
    _validate_cors_origins(["http://localhost:3000"])


def test_loopback_dev_accepted() -> None:
    _validate_cors_origins(["http://127.0.0.1:5173"])


def test_multiple_https_origins_accepted() -> None:
    _validate_cors_origins(
        ["https://app.acme.com", "https://admin.acme.com:443"]
    )


# ─── Refused configs ─────────────────────────────────────────────────


def test_plain_http_non_local_refused() -> None:
    """http:// to a non-localhost destination would carry session
    cookies in cleartext."""
    with pytest.raises(RuntimeError, match="unsafe origin"):
        _validate_cors_origins(["http://app.acme.com"])


def test_wildcard_mixed_with_explicit_refused() -> None:
    """Browsers reject this combination, but our middleware would
    flip credentials on regardless. Block at boot."""
    with pytest.raises(RuntimeError, match="alongside explicit"):
        _validate_cors_origins(["*", "https://app.acme.com"])


def test_garbage_origin_refused() -> None:
    """A typo / stray space doesn't silently widen the policy."""
    with pytest.raises(RuntimeError):
        _validate_cors_origins(["app.acme.com"])  # missing scheme


def test_origin_with_path_refused() -> None:
    """CORS origins must be scheme + host + optional port — no path."""
    with pytest.raises(RuntimeError):
        _validate_cors_origins(["https://app.acme.com/api"])
