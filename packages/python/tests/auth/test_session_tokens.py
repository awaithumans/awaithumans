"""Session-cookie HMAC — signing, verify, tamper, expiry."""

from __future__ import annotations

import base64
import json
import time

import pytest

from awaithumans.server.core.auth import (
    InvalidSessionError,
    sign_session,
    verify_password,
    verify_session,
)
from awaithumans.server.core.config import settings
from awaithumans.utils.constants import HMAC_SHA256_DIGEST_BYTES


def test_roundtrip(auth_enabled) -> None:
    token = sign_session(user="admin")
    assert verify_session(token) == "admin"


def test_sessions_vary_by_time(auth_enabled) -> None:
    """Two sessions minted at different times must differ (expiry is signed)."""
    a = sign_session(user="admin")
    time.sleep(1.1)  # tokens embed int(time.time()) so 1s resolution
    b = sign_session(user="admin")
    assert a != b


def test_tampered_body_rejected(auth_enabled) -> None:
    token = sign_session(user="admin")
    raw = bytearray(base64.urlsafe_b64decode(token + "=" * (-len(token) % 4)))
    raw[-1] ^= 0x01  # flip a bit in the body
    tampered = base64.urlsafe_b64encode(bytes(raw)).decode().rstrip("=")
    with pytest.raises(InvalidSessionError):
        verify_session(tampered)


def test_tampered_mac_rejected(auth_enabled) -> None:
    token = sign_session(user="admin")
    raw = bytearray(base64.urlsafe_b64decode(token + "=" * (-len(token) % 4)))
    raw[0] ^= 0x01  # flip a bit in the mac
    tampered = base64.urlsafe_b64encode(bytes(raw)).decode().rstrip("=")
    with pytest.raises(InvalidSessionError):
        verify_session(tampered)


def test_expired_rejected(auth_enabled) -> None:
    token = sign_session(user="admin", ttl_seconds=-1)
    with pytest.raises(InvalidSessionError, match="expired"):
        verify_session(token)


def test_empty_rejected(auth_enabled) -> None:
    with pytest.raises(InvalidSessionError):
        verify_session("")


def test_bad_base64_rejected(auth_enabled) -> None:
    with pytest.raises(InvalidSessionError):
        verify_session("!!!not base64!!!")


def test_too_short_rejected(auth_enabled) -> None:
    short = base64.urlsafe_b64encode(b"x" * (HMAC_SHA256_DIGEST_BYTES - 1)).decode()
    with pytest.raises(InvalidSessionError):
        verify_session(short)


def test_malformed_body_rejected(auth_enabled) -> None:
    """Valid HMAC but body isn't the expected {u, e} shape."""
    from awaithumans.server.core.auth import _hmac_key
    import hashlib
    import hmac as hmac_mod

    body = b'{"not": "our shape"}'
    mac = hmac_mod.new(_hmac_key(), body, hashlib.sha256).digest()
    token = base64.urlsafe_b64encode(mac + body).decode().rstrip("=")
    with pytest.raises(InvalidSessionError, match="malformed"):
        verify_session(token)


def test_password_check_correct(auth_enabled) -> None:
    assert verify_password(user="admin", password="correct-horse-battery-staple")


def test_password_check_wrong_password(auth_enabled) -> None:
    assert not verify_password(user="admin", password="wrong")


def test_password_check_wrong_user(auth_enabled) -> None:
    assert not verify_password(user="somebody-else", password="correct-horse-battery-staple")


def test_password_check_auth_disabled(auth_disabled) -> None:
    """When DASHBOARD_PASSWORD is unset, verify_password always rejects."""
    assert not verify_password(user="admin", password="admin")
