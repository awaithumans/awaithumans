"""OpenAI verifier.

Uses OpenAI's structured-output (JSON schema response_format) to force
the model to fill VERIFIER_OUTPUT_SCHEMA. Same shape as the Claude
verifier so the runner can swap providers without touching state."""

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
from awaithumans.types import VerificationContext, VerifierConfig, VerifierResult

DEFAULT_MODEL = "gpt-4o-2024-11-20"
DEFAULT_API_KEY_ENV = "OPENAI_API_KEY"


async def verify(config: VerifierConfig, ctx: VerificationContext) -> VerifierResult:
    try:
        from openai import AsyncOpenAI
    except ImportError as exc:
        raise VerifierProviderUnavailableError("openai", "verifier-openai") from exc

    api_key_env = config.api_key_env or DEFAULT_API_KEY_ENV
    api_key = os.environ.get(api_key_env)
    if not api_key:
        raise VerifierAPIKeyMissingError(api_key_env)

    client = AsyncOpenAI(api_key=api_key)
    model = config.model or DEFAULT_MODEL

    # OpenAI's JSON-schema response_format requires `additionalProperties:
    # false` and every property listed in `required`. Our shared schema
    # leaves parsed_response optional (not all tasks need NL parsing) so
    # we transform once here rather than polluting the shared schema.
    strict_schema = _to_strict_schema(VERIFIER_OUTPUT_SCHEMA)

    try:
        response = await client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": build_system_prompt(config.instructions)},
                {"role": "user", "content": build_user_prompt(ctx)},
            ],
            response_format={
                "type": "json_schema",
                "json_schema": {
                    "name": "verifier_verdict",
                    "schema": strict_schema,
                    "strict": True,
                },
            },
            max_tokens=1024,
        )
    except Exception as exc:  # noqa: BLE001
        raise VerifierProviderError("openai", str(exc)) from exc

    content = response.choices[0].message.content
    if not content:
        raise VerifierProviderError("openai", "Empty response content.")

    try:
        payload = json.loads(content)
    except json.JSONDecodeError as exc:
        raise VerifierProviderError("openai", f"Response was not valid JSON: {exc.msg}") from exc

    return VerifierResult(
        passed=bool(payload.get("passed", False)),
        reason=str(payload.get("reason", "")),
        parsed_response=payload.get("parsed_response"),
    )


def _to_strict_schema(schema: dict) -> dict:
    """Adapt the shared output schema for OpenAI's strict mode.

    Strict mode requires every property be in `required` and the object
    set `additionalProperties: false`. We promote `parsed_response` into
    `required` and let the model emit `null` when there's no NL parsing
    to do — strict mode allows nulls when the type union includes them."""
    strict = json.loads(json.dumps(schema))  # deep copy
    strict["additionalProperties"] = False
    strict["required"] = list(strict.get("properties", {}).keys())
    # Allow parsed_response to be null; it's optional in spirit.
    if "parsed_response" in strict.get("properties", {}):
        strict["properties"]["parsed_response"]["type"] = [
            "object",
            "string",
            "number",
            "boolean",
            "array",
            "null",
        ]
    return strict
