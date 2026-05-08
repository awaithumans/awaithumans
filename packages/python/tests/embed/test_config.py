"""Settings exposure for embed-related env vars.

Tests that the three new fields exist on Settings with the expected
defaults and types. The `env_prefix = "AWAITHUMANS_"` declared in
config.py's model_config means env vars use the prefixed names
(`AWAITHUMANS_EMBED_SIGNING_SECRET`, etc.); the field names on Settings
omit the prefix.

Tests assert directly against the settings singleton rather than
reloading the config module — `importlib.reload(config_module)` leaves
a half-reloaded class in sys.modules, which breaks unrelated tests that
imported `settings` before reload (the auth-suite `_isolated_db`
fixture saves `conn._async_engine`, and the reload-driven dance ends up
with mismatched module references).
"""

from __future__ import annotations

from awaithumans.server.core.config import Settings, settings


def test_settings_class_has_embed_signing_secret_field() -> None:
    assert "EMBED_SIGNING_SECRET" in Settings.model_fields


def test_settings_class_has_embed_parent_origins_field() -> None:
    assert "EMBED_PARENT_ORIGINS" in Settings.model_fields


def test_settings_class_has_service_api_key_field() -> None:
    assert "SERVICE_API_KEY" in Settings.model_fields


def test_embed_signing_secret_default_is_none() -> None:
    info = Settings.model_fields["EMBED_SIGNING_SECRET"]
    assert info.default is None


def test_embed_parent_origins_default_is_empty_string() -> None:
    info = Settings.model_fields["EMBED_PARENT_ORIGINS"]
    assert info.default == ""


def test_service_api_key_default_is_none() -> None:
    info = Settings.model_fields["SERVICE_API_KEY"]
    assert info.default is None


def test_settings_singleton_exposes_fields() -> None:
    """Smoke check that the live singleton object has all three attrs."""
    assert hasattr(settings, "EMBED_SIGNING_SECRET")
    assert hasattr(settings, "EMBED_PARENT_ORIGINS")
    assert hasattr(settings, "SERVICE_API_KEY")
