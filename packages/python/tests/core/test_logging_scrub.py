"""Log-scrubber redacts API keys / passwords / bearer tokens.

The scrubber sits on the root logger's handler so even careless calls
like `logger.info("body=%s", request.body)` can't leak secrets to the
log aggregator. These tests pin the patterns; a regression would mean
real credentials in production logs."""

from __future__ import annotations

from awaithumans.server.core.logging_config import scrub_text


def test_scrubs_openai_anthropic_style_key() -> None:
    out = scrub_text("Authentication failed: sk-ant-api03-AbCdEfGhIjKlMnOp")
    assert "sk-ant" not in out
    assert "[REDACTED]" in out


def test_scrubs_stripe_style_scoped_key() -> None:
    out = scrub_text("got sk_live_AbCdEfGhIjKlMnOp from billing")
    assert "sk_live_" not in out
    assert "[REDACTED]" in out


def test_scrubs_bearer_token() -> None:
    out = scrub_text("Authorization: Bearer eyJhbGc.foo.bar")
    assert "eyJhbGc" not in out
    assert "[REDACTED]" in out


def test_scrubs_google_api_key() -> None:
    out = scrub_text(
        "POST https://generativelanguage.googleapis.com/?key=AIzaSyExample1234567890ExampleKey1234567890"
    )
    assert "AIza" not in out


def test_scrubs_password_in_json() -> None:
    out = scrub_text('login attempt: {"email":"a@b","password":"hunter2"}')
    assert "hunter2" not in out
    assert "password" in out  # field name preserved
    assert "[REDACTED]" in out


def test_scrubs_password_query_param_style() -> None:
    out = scrub_text("password=hunter2 logged from form")
    assert "hunter2" not in out


def test_scrubs_x_admin_token_header_line() -> None:
    out = scrub_text("X-Admin-Token: secret-admin-value-1234")
    assert "secret-admin-value-1234" not in out
    assert "[REDACTED]" in out


def test_scrubber_idempotent() -> None:
    """Running the scrubber twice shouldn't double-redact or wreck
    already-cleaned text."""
    once = scrub_text("Bearer abc")
    twice = scrub_text(once)
    assert twice == once


def test_no_match_passes_through() -> None:
    """Plain text without secrets is unchanged."""
    msg = "Task abc completed in 3.2s"
    assert scrub_text(msg) == msg
