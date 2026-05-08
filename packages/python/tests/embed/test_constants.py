"""Tests for dashboard embedding constants."""

from __future__ import annotations

from awaithumans.utils import constants


def test_embed_token_default_ttl() -> None:
    """Test EMBED_TOKEN_DEFAULT_TTL_SECONDS is defined."""
    assert hasattr(constants, "EMBED_TOKEN_DEFAULT_TTL_SECONDS")
    assert constants.EMBED_TOKEN_DEFAULT_TTL_SECONDS == 300


def test_embed_token_max_ttl() -> None:
    """Test EMBED_TOKEN_MAX_TTL_SECONDS is defined."""
    assert hasattr(constants, "EMBED_TOKEN_MAX_TTL_SECONDS")
    assert constants.EMBED_TOKEN_MAX_TTL_SECONDS == 3600


def test_embed_token_min_ttl() -> None:
    """Test EMBED_TOKEN_MIN_TTL_SECONDS is defined."""
    assert hasattr(constants, "EMBED_TOKEN_MIN_TTL_SECONDS")
    assert constants.EMBED_TOKEN_MIN_TTL_SECONDS == 60


def test_embed_token_audience() -> None:
    """Test EMBED_TOKEN_AUDIENCE is defined."""
    assert hasattr(constants, "EMBED_TOKEN_AUDIENCE")
    assert constants.EMBED_TOKEN_AUDIENCE == "embed"


def test_embed_token_issuer() -> None:
    """Test EMBED_TOKEN_ISSUER is defined."""
    assert hasattr(constants, "EMBED_TOKEN_ISSUER")
    assert constants.EMBED_TOKEN_ISSUER == "awaithumans"


def test_embed_token_leeway() -> None:
    """Test EMBED_TOKEN_LEEWAY_SECONDS is defined."""
    assert hasattr(constants, "EMBED_TOKEN_LEEWAY_SECONDS")
    assert constants.EMBED_TOKEN_LEEWAY_SECONDS == 60


def test_service_key_prefix() -> None:
    """Test SERVICE_KEY_PREFIX is defined."""
    assert hasattr(constants, "SERVICE_KEY_PREFIX")
    assert constants.SERVICE_KEY_PREFIX == "ah_sk_"


def test_service_key_raw_bytes() -> None:
    """Test SERVICE_KEY_RAW_BYTES is defined."""
    assert hasattr(constants, "SERVICE_KEY_RAW_BYTES")
    assert constants.SERVICE_KEY_RAW_BYTES == 20


def test_service_key_display_prefix_length() -> None:
    """Test SERVICE_KEY_DISPLAY_PREFIX_LENGTH is defined."""
    assert hasattr(constants, "SERVICE_KEY_DISPLAY_PREFIX_LENGTH")
    assert constants.SERVICE_KEY_DISPLAY_PREFIX_LENGTH == 12


def test_service_key_max_name_length() -> None:
    """Test SERVICE_KEY_MAX_NAME_LENGTH is defined."""
    assert hasattr(constants, "SERVICE_KEY_MAX_NAME_LENGTH")
    assert constants.SERVICE_KEY_MAX_NAME_LENGTH == 80
