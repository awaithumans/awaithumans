"""Azure OpenAI verifier configuration helper.

Usage:
    from awaithumans.verifiers.azure_openai import azure_openai_verifier

    result = await await_human(
        task="Approve this KYC?",
        ...,
        verifier=azure_openai_verifier(
            instructions="Check that the decision is consistent with the AI confidence score.",
            deployment_name="gpt-4o",
            max_attempts=3,
        ),
    )

Requires: pip install "awaithumans[verifier-azure]"
The actual verification runs SERVER-SIDE. This helper just creates the config.
"""

from __future__ import annotations

from awaithumans.types import VerifierConfig


def azure_openai_verifier(
    instructions: str,
    *,
    deployment_name: str = "gpt-4o",
    max_attempts: int = 3,
    api_key_env: str = "AZURE_OPENAI_API_KEY",
    endpoint_env: str = "AZURE_OPENAI_ENDPOINT",
    api_version: str = "2024-10-21",
) -> VerifierConfig:
    """Create an Azure OpenAI verifier configuration.

    The actual LLM call runs on the awaithumans server, not in the SDK.
    This helper creates the config object that tells the server what to do.

    Azure OpenAI uses deployment names instead of model names, and requires
    an endpoint URL in addition to the API key.

    Args:
        instructions: The verification prompt. Describe what to check.
        deployment_name: Azure OpenAI deployment name.
        max_attempts: Max verification attempts before exhaustion.
        api_key_env: Environment variable name for the Azure API key.
        endpoint_env: Environment variable name for the Azure endpoint URL.
        api_version: Azure OpenAI API version.
    """
    return VerifierConfig(
        provider="azure_openai",
        model=deployment_name,
        instructions=instructions,
        max_attempts=max_attempts,
        api_key_env=api_key_env,
        metadata={
            "endpoint_env": endpoint_env,
            "api_version": api_version,
        },
    )
