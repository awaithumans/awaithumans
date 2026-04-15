"""Verifier configurations — one file per LLM provider.

Usage:
    from awaithumans.verifiers.claude import claude_verifier
    from awaithumans.verifiers.openai import openai_verifier
    from awaithumans.verifiers.gemini import gemini_verifier
    from awaithumans.verifiers.azure_openai import azure_openai_verifier

All verifiers create a VerifierConfig object that is sent to the server.
The server executes the actual LLM call. The SDK never calls the LLM directly.
"""
