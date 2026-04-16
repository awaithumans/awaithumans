"""Google Gemini verifier configuration helper.

Usage:
    from awaithumans.verifiers.gemini import gemini_verifier

    result = await await_human(
        task="Approve this KYC?",
        ...,
        verifier=gemini_verifier(
            instructions="Check that the decision is consistent with the AI confidence score.",
            max_attempts=3,
        ),
    )

Requires: pip install "awaithumans[verifier-gemini]"
The actual verification runs SERVER-SIDE. This helper just creates the config.
"""

from __future__ import annotations

from awaithumans.types import VerifierConfig


def gemini_verifier(
    instructions: str,
    *,
    model: str = "gemini-2.5-flash",
    max_attempts: int = 3,
    api_key_env: str = "GOOGLE_API_KEY",
) -> VerifierConfig:
    """Create a Google Gemini verifier configuration.

    The actual LLM call runs on the awaithumans server, not in the SDK.
    This helper creates the config object that tells the server what to do.

    Args:
        instructions: The verification prompt. Describe what to check.
        model: Gemini model to use.
        max_attempts: Max verification attempts before exhaustion.
        api_key_env: Environment variable name for the API key (read by the server).
    """
    return VerifierConfig(
        provider="gemini",
        model=model,
        instructions=instructions,
        max_attempts=max_attempts,
        api_key_env=api_key_env,
    )
