"""Verifier runner — dispatches a VerifierConfig to the right provider.

The runner is the single entry point for verification. Callers (the
task-completion path in `task_service`) call `run_verifier()`; the
runner picks a provider module by `config.provider` and awaits its
`verify()` function.

Provider failures (network, auth, missing extra) raise typed
ServiceError subclasses — the central FastAPI exception handler turns
those into HTTP responses with `error_code` + `docs_url`. The caller
distinguishes "the LLM said this response is bad" (a normal `passed=
False` VerifierResult) from "the LLM call itself blew up" (an
exception) — only the former counts toward `max_attempts`.
"""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable

from awaithumans.server.services.exceptions import VerifierProviderUnknownError
from awaithumans.server.verification.providers import (
    azure_openai as azure_provider,
)
from awaithumans.server.verification.providers import (
    claude as claude_provider,
)
from awaithumans.server.verification.providers import (
    gemini as gemini_provider,
)
from awaithumans.server.verification.providers import (
    openai as openai_provider,
)
from awaithumans.types import VerificationContext, VerifierConfig, VerifierResult

logger = logging.getLogger("awaithumans.server.verification")

VerifyFn = Callable[[VerifierConfig, VerificationContext], Awaitable[VerifierResult]]

# Map config.provider → provider verify function. Adding a new provider
# is one line here + one new file in providers/. The list of keys is
# also what we surface back to operators in VerifierProviderUnknownError
# so they see the supported set in the error message.
_PROVIDERS: dict[str, VerifyFn] = {
    "claude": claude_provider.verify,
    "anthropic": claude_provider.verify,  # alias — anthropic-the-vendor
    "openai": openai_provider.verify,
    "gemini": gemini_provider.verify,
    "google": gemini_provider.verify,  # alias
    "azure": azure_provider.verify,
    "azure_openai": azure_provider.verify,  # alias
}


async def run_verifier(config: VerifierConfig, ctx: VerificationContext) -> VerifierResult:
    """Run verification for one attempt.

    Returns a VerifierResult — `passed=True` means the response is
    accepted (and `parsed_response` carries the structured value when
    NL-parsed). `passed=False` is a normal verifier rejection; the
    caller decides whether to retry or mark exhausted.

    Raises ServiceError subclasses for provider-level failures (missing
    SDK extra, bad API key, vendor outage) — those don't count as a
    'rejection' and shouldn't decrement the human's retry budget."""
    verify_fn = _PROVIDERS.get(config.provider.lower().strip())
    if verify_fn is None:
        raise VerifierProviderUnknownError(config.provider, sorted(set(_PROVIDERS.keys())))

    logger.info(
        "Running verifier provider=%s model=%s attempt=%d",
        config.provider,
        config.model,
        ctx.attempt,
    )
    result = await verify_fn(config, ctx)
    logger.info(
        "Verifier verdict provider=%s passed=%s reason=%r",
        config.provider,
        result.passed,
        result.reason[:100],
    )
    return result
