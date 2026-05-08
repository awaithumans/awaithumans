"""Embed-specific ServiceError subclasses.

The central exception handler in core/exceptions.py builds the HTTP
response from these classes' status_code/error_code; no per-exception
handler is needed. Convention: error_code is UPPERCASE_SNAKE_CASE.
"""

from __future__ import annotations

from awaithumans.server.services.exceptions import (
    EmbedOriginNotAllowedError,
    InvalidEmbedTokenError,
    ServiceError,
    ServiceKeyNotFoundError,
)


def test_invalid_embed_token_is_service_error() -> None:
    err = InvalidEmbedTokenError(reason="bad signature")
    assert isinstance(err, ServiceError)
    assert err.status_code == 401
    assert err.error_code == "INVALID_EMBED_TOKEN"
    assert "bad signature" in str(err)


def test_invalid_embed_token_carries_reason() -> None:
    err = InvalidEmbedTokenError(reason="expired")
    assert err.reason == "expired"


def test_embed_origin_not_allowed_is_service_error() -> None:
    err = EmbedOriginNotAllowedError(origin="https://evil.example")
    assert isinstance(err, ServiceError)
    assert err.status_code == 400
    assert err.error_code == "EMBED_ORIGIN_NOT_ALLOWED"
    assert "evil.example" in str(err)


def test_embed_origin_not_allowed_carries_origin() -> None:
    err = EmbedOriginNotAllowedError(origin="https://evil.example")
    assert err.origin == "https://evil.example"


def test_service_key_not_found_is_service_error() -> None:
    err = ServiceKeyNotFoundError()
    assert isinstance(err, ServiceError)
    assert err.status_code == 401
    assert err.error_code == "SERVICE_KEY_NOT_FOUND"
