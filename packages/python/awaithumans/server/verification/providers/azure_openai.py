"""Azure OpenAI verifier.

Same wire format as the OpenAI provider — Azure OpenAI is API-compatible
with OpenAI's chat completions, just with a different base URL +
deployment-name addressing.

Reads three things from VerifierConfig.metadata:
  - endpoint_env  (default: AZURE_OPENAI_ENDPOINT) — full base URL
  - api_version   (default: 2024-10-21)
  - deployment    — Azure deployment name (required; goes in `model` slot)

`config.api_key_env` defaults to `AZURE_OPENAI_API_KEY`.
"""

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
from awaithumans.server.verification.providers.openai import _to_strict_schema
from awaithumans.types import VerificationContext, VerifierConfig, VerifierResult
from awaithumans.utils.constants import (
    VERIFIER_AZURE_DEFAULT_API_KEY_ENV,
    VERIFIER_AZURE_DEFAULT_API_VERSION,
    VERIFIER_AZURE_DEFAULT_ENDPOINT_ENV,
    VERIFIER_MAX_OUTPUT_TOKENS,
    VERIFIER_OUTPUT_SCHEMA_NAME,
)


async def verify(config: VerifierConfig, ctx: VerificationContext) -> VerifierResult:
    try:
        from openai import AsyncAzureOpenAI
    except ImportError as exc:
        raise VerifierProviderUnavailableError("azure", "verifier-azure") from exc

    api_key_env = config.api_key_env or VERIFIER_AZURE_DEFAULT_API_KEY_ENV
    api_key = os.environ.get(api_key_env)
    if not api_key:
        raise VerifierAPIKeyMissingError(api_key_env)

    metadata = config.metadata or {}
    endpoint_env = metadata.get("endpoint_env", VERIFIER_AZURE_DEFAULT_ENDPOINT_ENV)
    endpoint = os.environ.get(endpoint_env)
    if not endpoint:
        raise VerifierAPIKeyMissingError(endpoint_env)

    api_version = metadata.get("api_version", VERIFIER_AZURE_DEFAULT_API_VERSION)
    deployment = metadata.get("deployment") or config.model
    if not deployment:
        raise VerifierProviderError(
            "azure",
            "Azure OpenAI requires a deployment name. Set it in "
            "VerifierConfig.metadata['deployment'] or .model.",
        )

    client = AsyncAzureOpenAI(
        api_key=api_key,
        azure_endpoint=endpoint,
        api_version=api_version,
    )

    strict_schema = _to_strict_schema(VERIFIER_OUTPUT_SCHEMA)

    try:
        response = await client.chat.completions.create(
            model=deployment,  # for Azure, "model" is the deployment name
            messages=[
                {"role": "system", "content": build_system_prompt(config.instructions)},
                {"role": "user", "content": build_user_prompt(ctx)},
            ],
            response_format={
                "type": "json_schema",
                "json_schema": {
                    "name": VERIFIER_OUTPUT_SCHEMA_NAME,
                    "schema": strict_schema,
                    "strict": True,
                },
            },
            max_tokens=VERIFIER_MAX_OUTPUT_TOKENS,
        )
    except Exception as exc:  # noqa: BLE001
        raise VerifierProviderError("azure", str(exc)) from exc

    content = response.choices[0].message.content
    if not content:
        raise VerifierProviderError("azure", "Empty response content.")

    try:
        payload = json.loads(content)
    except json.JSONDecodeError as exc:
        raise VerifierProviderError("azure", f"Response was not valid JSON: {exc.msg}") from exc

    return VerifierResult(
        passed=bool(payload.get("passed", False)),
        reason=str(payload.get("reason", "")),
        parsed_response=payload.get("parsed_response"),
    )
