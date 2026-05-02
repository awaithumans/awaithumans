"""`Settings.get_secret` is the single sanctioned env-var read point.

Verifier providers (and any future code path with the same need) call
`settings.get_secret(env_name)` instead of `os.environ.get(env_name)`.
This decouples consumers from CLAUDE.md's "no raw os.environ outside
core/config.py" rule and gives us one place to add scrubbing / audit /
.env normalisation later."""

from __future__ import annotations

from collections.abc import Iterator

import pytest

from awaithumans.server.core.config import settings


@pytest.fixture(autouse=True)
def _isolate_env(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Each test starts with a clean ANTHROPIC_API_KEY field."""
    original = settings.ANTHROPIC_API_KEY
    settings.ANTHROPIC_API_KEY = None
    yield
    settings.ANTHROPIC_API_KEY = original


def test_returns_value_from_settings_field(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When the env var matches a declared Settings field, prefer the
    pydantic-loaded value (which honours `.env` files)."""
    settings.ANTHROPIC_API_KEY = "from-settings"
    monkeypatch.setenv("ANTHROPIC_API_KEY", "from-os-environ")
    assert settings.get_secret("ANTHROPIC_API_KEY") == "from-settings"


def test_falls_back_to_os_environ_for_undeclared_var(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Operators can name their key env var anything via
    VerifierConfig.api_key_env — we don't pre-declare every possible
    name. Falling back to os.environ catches those cases."""
    monkeypatch.setenv("CUSTOM_VERIFIER_KEY", "lookup-me")
    assert settings.get_secret("CUSTOM_VERIFIER_KEY") == "lookup-me"


def test_returns_none_when_unset(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("DOES_NOT_EXIST_AT_ALL", raising=False)
    assert settings.get_secret("DOES_NOT_EXIST_AT_ALL") is None


def test_empty_string_treated_as_unset(monkeypatch: pytest.MonkeyPatch) -> None:
    """Operators sometimes set an env var to empty (`KEY=`); treat that
    the same as missing so the verifier raises a clear
    VerifierAPIKeyMissingError instead of an opaque vendor 401."""
    monkeypatch.setenv("MAYBE_EMPTY", "")
    assert settings.get_secret("MAYBE_EMPTY") is None


def test_case_insensitive_match_on_settings_field(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Pydantic-settings is case-insensitive (we set
    `case_sensitive=False`). The lookup matches whether the caller
    passes uppercase or lowercase."""
    settings.ANTHROPIC_API_KEY = "uppercase-set"
    assert settings.get_secret("anthropic_api_key") == "uppercase-set"
