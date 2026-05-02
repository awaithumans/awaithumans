"""Anthropic Claude verifier.

Uses Anthropic's tool-use mechanism to force structured output. The
"verdict" tool's input schema mirrors VERIFIER_OUTPUT_SCHEMA and
that's the only tool offered, so the model is constrained to fill it.

Lazy-imports `anthropic` so `awaithumans[server]` without
`awaithumans[verifier-claude]` still imports cleanly."""

from __future__ import annotations

import json
import os

from awaithumans.server.services.exceptions import (
    VerifierAPIKeyMissingError,
    VerifierProviderError,
    VerifierProviderUnavailableError,
)
from awaithumans.server.verification.prompt import (
    VERIFIER_OUTPUT_SCHEMA,
    build_system_prompt,
    build_user_prompt,
)
from awaithumans.server.verification.providers import sanitize_provider_error_detail
from awaithumans.types import VerificationContext, VerifierConfig, VerifierResult
from awaithumans.utils.constants import (
    VERIFIER_CLAUDE_DEFAULT_API_KEY_ENV,
    VERIFIER_CLAUDE_DEFAULT_MODEL,
    VERIFIER_CLAUDE_TOOL_NAME,
    VERIFIER_MAX_OUTPUT_TOKENS,
)


async def verify(config: VerifierConfig, ctx: VerificationContext) -> VerifierResult:
    try:
        from anthropic import AsyncAnthropic
    except ImportError as exc:
        raise VerifierProviderUnavailableError("claude", "verifier-claude") from exc

    api_key_env = config.api_key_env or VERIFIER_CLAUDE_DEFAULT_API_KEY_ENV
    api_key = os.environ.get(api_key_env)
    if not api_key:
        raise VerifierAPIKeyMissingError(api_key_env)

    client = AsyncAnthropic(api_key=api_key)
    model = config.model or VERIFIER_CLAUDE_DEFAULT_MODEL

    try:
        response = await client.messages.create(
            model=model,
            max_tokens=VERIFIER_MAX_OUTPUT_TOKENS,
            system=build_system_prompt(config.instructions),
            messages=[{"role": "user", "content": build_user_prompt(ctx)}],
            tools=[
                {
                    "name": VERIFIER_CLAUDE_TOOL_NAME,
                    "description": "Submit your verification verdict.",
                    "input_schema": VERIFIER_OUTPUT_SCHEMA,
                }
            ],
            tool_choice={"type": "tool", "name": VERIFIER_CLAUDE_TOOL_NAME},
        )
    except Exception as exc:  # noqa: BLE001 — vendor SDK exceptions vary
        raise VerifierProviderError("claude", sanitize_provider_error_detail(str(exc))) from exc

    # The forced tool_choice guarantees a tool_use block. Defensive parse
    # anyway — if Anthropic ever changes the contract we want a clear
    # error, not a NoneType crash three layers down.
    for block in response.content:
        if getattr(block, "type", None) == "tool_use" and block.name == VERIFIER_CLAUDE_TOOL_NAME:
            payload = block.input
            if not isinstance(payload, dict):
                payload = json.loads(payload) if isinstance(payload, str) else {}
            return _to_result(payload)

    raise VerifierProviderError(
        "claude",
        "Claude returned no tool_use block — model contract may have changed.",
    )


def _to_result(payload: dict) -> VerifierResult:
    return VerifierResult(
        passed=bool(payload.get("passed", False)),
        reason=str(payload.get("reason", "")),
        parsed_response=payload.get("parsed_response"),
    )
