"""Verification execution — runs AI verifiers server-side.

Public surface is `run_verifier()`. Wire it into the task-completion
path so a task with a `verifier_config` runs through the verifier
before reaching a terminal status.

Provider implementations are lazy — they only import their vendor SDK
when actually called. Missing extras surface as
`VerifierProviderUnavailableError` with the exact `pip install` line."""

from __future__ import annotations

from awaithumans.server.verification.runner import run_verifier

__all__ = ["run_verifier"]
