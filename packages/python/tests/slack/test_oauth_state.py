"""OAuth state signing — round-trip + tamper detection + expiry."""

from __future__ import annotations

import base64
import time
from unittest.mock import patch

from awaithumans.server.channels.slack.oauth_state import sign_state, verify_state
from awaithumans.utils.constants import SLACK_OAUTH_STATE_MAX_AGE_SECONDS

SECRET = "state-signing-secret"


def test_round_trip() -> None:
    state = sign_state(SECRET)
    assert verify_state(state, SECRET) is True


def test_wrong_secret_fails() -> None:
    state = sign_state(SECRET)
    assert verify_state(state, "other-secret") is False


def test_tampered_state_fails() -> None:
    state = sign_state(SECRET)
    # Flip a character in the middle — the HMAC won't match.
    pos = len(state) // 2
    tampered = state[:pos] + ("A" if state[pos] != "A" else "B") + state[pos + 1 :]
    assert verify_state(tampered, SECRET) is False


def test_expired_state_rejected() -> None:
    state = sign_state(SECRET)
    # Fast-forward past the max age.
    future = time.time() + SLACK_OAUTH_STATE_MAX_AGE_SECONDS + 1
    with patch("awaithumans.server.channels.slack.oauth_state.time.time", return_value=future):
        assert verify_state(state, SECRET) is False


def test_each_state_is_unique() -> None:
    """Nonce randomness: two states signed back-to-back differ."""
    a = sign_state(SECRET)
    b = sign_state(SECRET)
    assert a != b


def test_malformed_state_returns_false() -> None:
    assert verify_state("not-base64!@#$", SECRET) is False
    assert verify_state("", SECRET) is False
    assert verify_state(base64.urlsafe_b64encode(b"only-one-part").decode(), SECRET) is False


def test_empty_secret_returns_false() -> None:
    state = sign_state(SECRET)
    assert verify_state(state, "") is False
