"""Google Gemini verifier.

Uses Gemini's `response_schema` (structured output) to force the model
to fill VERIFIER_OUTPUT_SCHEMA. The `google-generativeai` SDK is sync;
we run it in a thread executor to keep the FastAPI handler async."""

from __future__ import annotations

import asyncio
import json
import os
from typing import Any

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
from awaithumans.utils.constants import (
    VERIFIER_GEMINI_DEFAULT_API_KEY_ENV,
    VERIFIER_GEMINI_DEFAULT_MODEL,
    VERIFIER_MAX_OUTPUT_TOKENS,
)


async def verify(config: VerifierConfig, ctx: VerificationContext) -> VerifierResult:
    try:
        import google.generativeai as genai
    except ImportError as exc:
        raise VerifierProviderUnavailableError("gemini", "verifier-gemini") from exc

    api_key_env = config.api_key_env or VERIFIER_GEMINI_DEFAULT_API_KEY_ENV
    api_key = os.environ.get(api_key_env)
    if not api_key:
        raise VerifierAPIKeyMissingError(api_key_env)

    model_name = config.model or VERIFIER_GEMINI_DEFAULT_MODEL
    system_prompt = build_system_prompt(config.instructions)
    user_prompt = build_user_prompt(ctx)

    def _call_sync() -> dict[str, Any]:
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel(
            model_name=model_name,
            system_instruction=system_prompt,
        )
        result = model.generate_content(
            user_prompt,
            generation_config={
                "response_mime_type": "application/json",
                "response_schema": _to_gemini_schema(VERIFIER_OUTPUT_SCHEMA),
                "max_output_tokens": VERIFIER_MAX_OUTPUT_TOKENS,
            },
        )
        return {"text": result.text}

    try:
        response = await asyncio.to_thread(_call_sync)
    except Exception as exc:  # noqa: BLE001
        raise VerifierProviderError("gemini", str(exc)) from exc

    text = response.get("text") or ""
    if not text:
        raise VerifierProviderError("gemini", "Empty response content.")

    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        raise VerifierProviderError("gemini", f"Response was not valid JSON: {exc.msg}") from exc

    return VerifierResult(
        passed=bool(payload.get("passed", False)),
        reason=str(payload.get("reason", "")),
        parsed_response=payload.get("parsed_response"),
    )


def _to_gemini_schema(schema: dict) -> dict:
    """Convert OpenAPI-ish schema to Gemini's expected shape.

    Gemini accepts a subset of OpenAPI schemas; in practice our shared
    schema is already compatible. Keeping this as a translation point
    in case Gemini's quirks diverge — they have historically rejected
    unknown keys, so we strip anything they don't grok."""
    allowed_keys = {"type", "properties", "required", "description", "items", "enum"}
    return _strip_keys(schema, allowed_keys)


def _strip_keys(value: Any, allowed: set[str]) -> Any:
    if isinstance(value, dict):
        return {k: _strip_keys(v, allowed) for k, v in value.items() if k in allowed}
    if isinstance(value, list):
        return [_strip_keys(v, allowed) for v in value]
    return value
