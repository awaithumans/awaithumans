"""Password hashing — argon2id via argon2-cffi.

Argon2id is the OWASP-recommended default for new systems as of 2024
(memory-hard, side-channel-resistant, winner of the Password Hashing
Competition). The defaults in `argon2-cffi` match the minimum
parameters from RFC 9106; we don't tune them here.

Usage:

    from awaithumans.server.core.password import hash_password, verify_password
    h = hash_password("s3cret")
    verify_password("s3cret", h)        # True
    verify_password("wrong", h)         # False
"""

from __future__ import annotations

import logging

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError

logger = logging.getLogger("awaithumans.server.core.password")

# Module-level singleton — `PasswordHasher` is threadsafe and cheap to
# keep around. Expensive to construct on every call.
_hasher = PasswordHasher()


def hash_password(password: str) -> str:
    """Return an argon2id hash string (PHC format, fully self-describing)."""
    return _hasher.hash(password)


def verify_password(password: str, stored_hash: str) -> bool:
    """Constant-time verify. Returns False on mismatch or malformed hash;
    never raises on bad input — callers just see "wrong password." """
    try:
        return _hasher.verify(stored_hash, password)
    except VerifyMismatchError:
        return False
    except Exception as exc:  # malformed hash, unexpected algorithm, etc.
        logger.warning("password verify failed (treated as mismatch): %s", exc)
        return False
