"""Coverage gaps from the verifier code review.

Pins behaviours that aren't covered by `test_verifier_integration.py`:

  - `redact_payload=True` skips the verifier entirely (no LLM call,
    no leak of sensitive data to a third-party model).
  - `max_attempts=1` collapses to a single shot — first rejection is
    immediately VERIFICATION_EXHAUSTED.
  - Malformed `verifier_config` surfaces a typed
    VerifierConfigInvalidError, not a raw 500.
  - Unknown provider strings raise VerifierProviderUnknownError with
    the supported list in the message.
  - Provider-name aliases (`anthropic` / `google` / `azure_openai`)
    resolve to their canonical providers.
  - Vendor exception strings carrying API keys are scrubbed before
    being surfaced to the HTTP caller.
  - OpenAI strict-schema adapter promotes parsed_response to required
    + null-typed.
"""

from __future__ import annotations

from collections.abc import AsyncGenerator

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlmodel import SQLModel

from awaithumans.server.db.models import (  # noqa: F401 — register models
    AuditEntry,
    EmailSenderIdentity,
    SlackInstallation,
    Task,
)
from awaithumans.server.services import task_verifier
from awaithumans.server.services.exceptions import (
    VerifierConfigInvalidError,
    VerifierProviderUnknownError,
)
from awaithumans.server.services.task_service import complete_task, create_task
from awaithumans.server.verification.prompt import (
    VERIFIER_OUTPUT_SCHEMA,
    to_openai_strict_schema,
)
from awaithumans.server.verification.providers import sanitize_provider_error_detail
from awaithumans.server.verification.runner import _PROVIDERS
from awaithumans.types import TaskStatus, VerifierResult


@pytest_asyncio.fixture
async def session() -> AsyncGenerator[AsyncSession, None]:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
    factory = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as s:
        yield s
    await engine.dispose()


def _verifier_cfg(max_attempts: int = 3) -> dict:
    return {
        "provider": "claude",
        "model": "claude-sonnet-4-5",
        "instructions": "Check the decision is consistent.",
        "max_attempts": max_attempts,
        "api_key_env": "ANTHROPIC_API_KEY",
    }


# ─── redact_payload skips the verifier ───────────────────────────────


@pytest.mark.asyncio
async def test_redact_payload_skips_verifier_entirely(
    session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    """With `redact_payload=True` the verifier MUST NOT be called — the
    operator's payload would otherwise be shipped to the third-party
    LLM via the prompt. Status goes straight to COMPLETED."""
    task, _ = await create_task(
        session,
        task="Approve sensitive operation",
        payload={"ssn": "1234"},
        payload_schema={},
        response_schema={},
        timeout_seconds=900,
        idempotency_key="redact-test",
        verifier_config=_verifier_cfg(),
        redact_payload=True,
    )

    call_count = {"n": 0}

    async def boom(_cfg, _ctx):
        call_count["n"] += 1
        raise AssertionError(
            "Verifier was invoked despite redact_payload=True — payload "
            "would have leaked to the LLM."
        )

    monkeypatch.setattr(task_verifier, "run_verifier", boom)

    completed = await complete_task(session, task_id=task.id, response={"approved": True})
    assert completed.status == TaskStatus.COMPLETED
    assert completed.verifier_result is None
    assert completed.verification_attempt == 0
    assert call_count["n"] == 0


# ─── max_attempts edge case ──────────────────────────────────────────


@pytest.mark.asyncio
async def test_max_attempts_one_collapses_to_single_shot(
    session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`max_attempts=1` is the strictest setting — the operator gets
    one shot. The first rejection is immediately exhaustion (terminal),
    not REJECTED-with-zero-budget. Documents the off-by-one semantics."""
    task, _ = await create_task(
        session,
        task="One-shot verify",
        payload={},
        payload_schema={},
        response_schema={},
        timeout_seconds=900,
        idempotency_key="max-one",
        verifier_config=_verifier_cfg(max_attempts=1),
    )

    async def reject(_cfg, _ctx):
        return VerifierResult(passed=False, reason="No.")

    monkeypatch.setattr(task_verifier, "run_verifier", reject)

    out = await complete_task(session, task_id=task.id, response={"x": 1})
    assert out.status == TaskStatus.VERIFICATION_EXHAUSTED
    assert out.verification_attempt == 1


# ─── Malformed config ────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_malformed_verifier_config_surfaces_typed_error(
    session: AsyncSession,
) -> None:
    """A task whose `verifier_config` JSON is missing a required field
    must NOT 500 with a raw Pydantic ValidationError. The central
    handler turns VerifierConfigInvalidError into a clean 422 with an
    error_code + docs URL the operator can act on."""
    task, _ = await create_task(
        session,
        task="Bad config",
        payload={},
        payload_schema={},
        response_schema={},
        timeout_seconds=900,
        idempotency_key="bad-cfg",
        verifier_config={"provider": "claude"},  # missing `instructions`
    )

    with pytest.raises(VerifierConfigInvalidError) as excinfo:
        await complete_task(session, task_id=task.id, response={"x": 1})

    assert excinfo.value.error_code == "VERIFIER_CONFIG_INVALID"
    assert excinfo.value.status_code == 422


# ─── Unknown provider ────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_unknown_provider_raises_typed_error(
    session: AsyncSession,
) -> None:
    """Operator typos ('clade', 'gpt') should fail loudly with the
    supported provider list in the message — not a generic 500."""
    task, _ = await create_task(
        session,
        task="Bad provider",
        payload={},
        payload_schema={},
        response_schema={},
        timeout_seconds=900,
        idempotency_key="bad-provider",
        verifier_config={
            "provider": "clade",  # typo
            "instructions": "check",
        },
    )

    with pytest.raises(VerifierProviderUnknownError) as excinfo:
        await complete_task(session, task_id=task.id, response={"x": 1})

    assert excinfo.value.error_code == "VERIFIER_PROVIDER_UNKNOWN"
    # The supported set must be in the message so operators can fix
    # without hunting docs.
    msg = str(excinfo.value)
    assert "claude" in msg
    assert "openai" in msg


# ─── Provider aliases ────────────────────────────────────────────────


@pytest.mark.parametrize(
    "alias,canonical",
    [
        ("anthropic", "claude"),
        ("google", "gemini"),
        ("azure_openai", "azure"),
    ],
)
def test_provider_aliases_resolve(alias: str, canonical: str) -> None:
    """Documented vendor-name aliases must point at the same verify
    function as their canonical provider — operators reading the SDK
    error messages may try the obvious vendor name."""
    assert _PROVIDERS[alias] is _PROVIDERS[canonical]


# ─── API key sanitization ────────────────────────────────────────────


def test_sanitize_strips_openai_style_key() -> None:
    detail = sanitize_provider_error_detail(
        "401: Invalid API key sk-ant-api03-AbCdEfGhIjKlMnOpQrStUv"
    )
    assert "sk-ant" not in detail
    assert "[REDACTED]" in detail


def test_sanitize_strips_bearer_token() -> None:
    detail = sanitize_provider_error_detail(
        "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.payload.sig"
    )
    assert "Bearer" not in detail or "[REDACTED]" in detail
    assert "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.payload.sig" not in detail


def test_sanitize_strips_google_api_key() -> None:
    detail = sanitize_provider_error_detail(
        "Request failed: AIzaSyExample1234567890ExampleKey1234567890"
    )
    assert "AIza" not in detail
    assert "[REDACTED]" in detail


def test_sanitize_truncates_huge_detail() -> None:
    huge = "x" * 5000
    detail = sanitize_provider_error_detail(huge)
    assert len(detail) <= 500


# ─── OpenAI strict-schema adapter ────────────────────────────────────


def test_to_openai_strict_schema_promotes_parsed_response_to_required() -> None:
    """OpenAI strict mode requires every property be in `required` and
    `additionalProperties: false`. The adapter must add both without
    mutating the shared VERIFIER_OUTPUT_SCHEMA — that's read by every
    provider (including non-strict ones)."""
    out = to_openai_strict_schema(VERIFIER_OUTPUT_SCHEMA)

    assert out["additionalProperties"] is False
    assert "parsed_response" in out["required"]
    assert "null" in out["properties"]["parsed_response"]["type"]
    # Shared schema must be unchanged (deep copy).
    assert "additionalProperties" not in VERIFIER_OUTPUT_SCHEMA
