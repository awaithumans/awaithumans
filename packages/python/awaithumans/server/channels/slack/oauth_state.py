"""OAuth state parameter — signed nonce to prevent CSRF on the callback.

Slack's OAuth flow expects an opaque `state` value that we send to the
consent page and receive back on the callback. We don't want to store
state server-side (requires a new table and a cleanup job), so we make
it self-verifying: random nonce + timestamp + HMAC, base64-encoded.

    state = urlsafe_b64(f"{nonce}:{ts}:{hmac_hex(nonce:ts, secret)}")

On callback we decode, verify the HMAC, and reject anything older than
SLACK_OAUTH_STATE_MAX_AGE_SECONDS. The secret reused is
SLACK_SIGNING_SECRET, which is already set up for the webhook — one
Slack-related secret to configure, not two.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import logging
import secrets
import time

from awaithumans.utils.constants import SLACK_OAUTH_STATE_MAX_AGE_SECONDS

logger = logging.getLogger("awaithumans.server.channels.slack.oauth_state")


def sign_state(signing_secret: str) -> str:
    """Generate a signed state string for the OAuth consent URL."""
    nonce = secrets.token_urlsafe(16)
    ts = str(int(time.time()))
    payload = f"{nonce}:{ts}".encode()
    mac = hmac.new(signing_secret.encode(), payload, hashlib.sha256).hexdigest()
    raw = f"{nonce}:{ts}:{mac}".encode()
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def verify_state(state: str, signing_secret: str) -> bool:
    """Verify a state string from the OAuth callback. False on any failure."""
    if not state or not signing_secret:
        return False

    try:
        padded = state + "=" * (-len(state) % 4)
        decoded = base64.urlsafe_b64decode(padded).decode()
        nonce, ts, mac = decoded.rsplit(":", 2)
    except Exception:  # noqa: BLE001
        logger.warning("OAuth state: malformed or un-decodable.")
        return False

    payload = f"{nonce}:{ts}".encode()
    expected = hmac.new(signing_secret.encode(), payload, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, mac):
        logger.warning("OAuth state: HMAC mismatch.")
        return False

    try:
        age = abs(time.time() - int(ts))
    except ValueError:
        return False

    if age > SLACK_OAUTH_STATE_MAX_AGE_SECONDS:
        logger.warning("OAuth state: stale (age=%ds).", int(age))
        return False

    return True
