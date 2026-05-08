"""Settings exposure for embed-related env vars.

Settings uses `env_prefix = "AWAITHUMANS_"` (see config.py model_config),
so field names omit the prefix; env vars include it.
"""

from __future__ import annotations

import importlib

import pytest


@pytest.fixture
def reload_settings():
    """Reload settings under controlled env so each test is hermetic."""

    def _reload():
        from awaithumans.server.core import config as config_module

        importlib.reload(config_module)
        return config_module.settings

    return _reload


def test_embed_signing_secret_reads_from_env(
    monkeypatch: pytest.MonkeyPatch, reload_settings
) -> None:
    monkeypatch.setenv("AWAITHUMANS_EMBED_SIGNING_SECRET", "x" * 32)
    settings = reload_settings()
    assert settings.EMBED_SIGNING_SECRET == "x" * 32


def test_embed_signing_secret_default_is_none(
    monkeypatch: pytest.MonkeyPatch, reload_settings
) -> None:
    monkeypatch.delenv("AWAITHUMANS_EMBED_SIGNING_SECRET", raising=False)
    settings = reload_settings()
    assert settings.EMBED_SIGNING_SECRET is None


def test_embed_parent_origins_reads_from_env(
    monkeypatch: pytest.MonkeyPatch, reload_settings
) -> None:
    monkeypatch.setenv(
        "AWAITHUMANS_EMBED_PARENT_ORIGINS",
        "https://acme.com, https://*.acme.com",
    )
    settings = reload_settings()
    assert settings.EMBED_PARENT_ORIGINS == (
        "https://acme.com, https://*.acme.com"
    )


def test_embed_parent_origins_default_is_empty(
    monkeypatch: pytest.MonkeyPatch, reload_settings
) -> None:
    monkeypatch.delenv("AWAITHUMANS_EMBED_PARENT_ORIGINS", raising=False)
    settings = reload_settings()
    assert settings.EMBED_PARENT_ORIGINS == ""


def test_service_api_key_reads_from_env(
    monkeypatch: pytest.MonkeyPatch, reload_settings
) -> None:
    monkeypatch.setenv("AWAITHUMANS_SERVICE_API_KEY", "ah_sk_test")
    settings = reload_settings()
    assert settings.SERVICE_API_KEY == "ah_sk_test"


def test_service_api_key_default_is_none(
    monkeypatch: pytest.MonkeyPatch, reload_settings
) -> None:
    monkeypatch.delenv("AWAITHUMANS_SERVICE_API_KEY", raising=False)
    settings = reload_settings()
    assert settings.SERVICE_API_KEY is None
