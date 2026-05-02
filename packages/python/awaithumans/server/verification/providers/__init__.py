"""Verifier provider implementations.

One file per provider. Each exports `verify(config, context) ->
VerifierResult`. Lazy-imports its vendor SDK so missing extras only
break the verifier path that uses them, not the whole server."""

from __future__ import annotations

import re

# Vendor SDK exceptions sometimes carry the request URL (with auth
# query params) or echo back the API key in error bodies on certain
# auth failures. We bury that in a structured `VerifierProviderError`
# detail string that ends up in the HTTP response body — without
# scrubbing, a 502 could leak the operator's key to the human-facing
# channel.
#
# Patterns are conservative: anything that smells like a key
# prefix (`sk-...`, `Bearer ...`) or query-string auth gets redacted.
# The redaction target is `[REDACTED]` so a careful operator can spot
# scrubbing in their logs.
_KEY_PATTERNS = [
    re.compile(r"sk-[A-Za-z0-9_\-]{8,}"),  # OpenAI / Anthropic-style
    re.compile(r"sk_[a-z]+_[A-Za-z0-9_\-]{8,}"),  # Stripe / scoped variants
    re.compile(r"Bearer\s+[A-Za-z0-9_\-\.]+", re.IGNORECASE),
    re.compile(r"api[_-]?key\s*[:=]\s*['\"]?[A-Za-z0-9_\-]{8,}", re.IGNORECASE),
    re.compile(r"x-api-key:\s*[A-Za-z0-9_\-]{8,}", re.IGNORECASE),
    re.compile(r"AIza[A-Za-z0-9_\-]{35,}"),  # Google API key prefix
]

# Hard cap on the detail string we surface. Vendor errors can include
# entire response bodies (with payload echoes). 500 chars is enough to
# diagnose; more risks leaking task data the operator marked sensitive.
MAX_PROVIDER_ERROR_DETAIL_LEN = 500


def sanitize_provider_error_detail(raw: str) -> str:
    """Scrub API keys / bearer tokens from a vendor exception string.

    Used by every provider before raising `VerifierProviderError` so the
    HTTP response body never leaks credentials. Operators can still
    diagnose from server logs (which keep the unsanitized form via the
    chained `__cause__`)."""
    s = str(raw)
    for pattern in _KEY_PATTERNS:
        s = pattern.sub("[REDACTED]", s)
    if len(s) > MAX_PROVIDER_ERROR_DETAIL_LEN:
        s = s[: MAX_PROVIDER_ERROR_DETAIL_LEN - 3] + "..."
    return s
