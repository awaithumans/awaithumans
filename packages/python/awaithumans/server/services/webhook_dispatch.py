"""Outbound webhook dispatch for tasks with `callback_url`.

When an agent creates a task with `callback_url=...`, it's saying
"don't make me long-poll — push me when something changes." On every
terminal-status transition (COMPLETED, REJECTED-but-actually-no, etc.
— see `_should_dispatch`), the server sends a single HMAC-signed POST
to that URL with a JSON body summarising the outcome.

This is the foundation the durable-execution adapters (Temporal,
LangGraph) ride on: the user's web server registers a small handler
that verifies the HMAC, extracts the workflow identity, and signals
the workflow to resume.

Wire format:

    POST {callback_url}
    Content-Type: application/json
    X-Awaithumans-Signature: sha256=<hex>
    X-Awaithumans-Task-Id: <task_id>

    {
      "task_id": "...",
      "idempotency_key": "...",
      "status": "completed" | "timed_out" | "cancelled" | "verification_exhausted",
      "response": {...} | null,
      "completed_at": ISO8601 | null,
      "completed_by_email": str | null,
      "completed_via_channel": str | null,
      "verification_attempt": int
    }

Receivers should:
  1. Read the raw body as bytes.
  2. Recompute HMAC-SHA256(body) with their shared secret.
  3. Compare-digest against the `X-Awaithumans-Signature` header.
  4. Only then trust the JSON.

Delivery is fire-and-forget: a single attempt, ~10s timeout, log on
failure. Durability comes from the agent framework (Temporal's
own retry, LangGraph checkpoints) — we don't try to be a queue.
Operators who need at-least-once delivery should run the workflow
behind a system that already has it.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
from typing import Any

import httpx
from cryptography.hazmat.primitives.hashes import SHA256
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

from awaithumans.server.core.encryption import get_key
from awaithumans.server.db.models import Task
from awaithumans.utils.constants import (
    HMAC_SHA256_DIGEST_BYTES,
    WEBHOOK_DELIVERY_TIMEOUT_SECONDS,
    WEBHOOK_HKDF_INFO,
    WEBHOOK_HKDF_SALT,
    WEBHOOK_SIGNATURE_HEADER,
)

logger = logging.getLogger("awaithumans.server.services.webhook_dispatch")


def _hmac_key() -> bytes:
    """Derive a 32-byte HMAC key from PAYLOAD_KEY via HKDF-SHA256.

    Channel-scoped salt — the same root key signs sessions, magic
    links, AND webhooks, but each one derives a distinct subkey via
    HKDF so a leak of any one downstream key doesn't compromise the
    others."""
    return HKDF(
        algorithm=SHA256(),
        length=HMAC_SHA256_DIGEST_BYTES,
        salt=WEBHOOK_HKDF_SALT,
        info=WEBHOOK_HKDF_INFO,
    ).derive(get_key())


def sign_body(body: bytes) -> str:
    """Compute the `sha256=<hex>` signature header value.

    Public so callback handlers in the SDK adapters (and the docs
    examples) can use the same canonical computation when verifying
    incoming requests on the user's web server."""
    mac = hmac.new(_hmac_key(), body, hashlib.sha256).hexdigest()
    return f"sha256={mac}"


def verify_signature(*, body: bytes, signature: str | None) -> bool:
    """Constant-time check of the `X-Awaithumans-Signature` header.

    Used by the SDK adapters' callback handlers (Temporal, LangGraph)
    to verify incoming webhook bodies before signalling a workflow.
    `signature` is the header value as received (may include the
    `sha256=` prefix or just be the hex digest). Both shapes are
    accepted; missing/empty signatures fail closed."""
    if not signature:
        return False
    expected = sign_body(body)
    if hmac.compare_digest(signature, expected):
        return True
    # Tolerate header-value-without-prefix (some routing layers strip).
    return hmac.compare_digest(signature, expected.removeprefix("sha256="))


def _build_payload(task: Task) -> dict[str, Any]:
    """The JSON body the receiver gets. Designed to be self-contained
    so the receiver doesn't need a second round-trip to figure out
    what happened."""
    return {
        "task_id": task.id,
        "idempotency_key": task.idempotency_key,
        "status": task.status.value,
        "response": task.response,
        "completed_at": task.completed_at.isoformat() if task.completed_at else None,
        "timed_out_at": task.timed_out_at.isoformat() if task.timed_out_at else None,
        "completed_by_email": task.completed_by_email,
        "completed_via_channel": task.completed_via_channel,
        "verification_attempt": task.verification_attempt,
    }


async def fire_completion_webhook(task: Task) -> None:
    """Single-attempt POST of the completion payload to `task.callback_url`.

    No-op if callback_url is unset. Network failures and non-2xx
    responses are logged, not retried; callers should treat this as
    fire-and-forget. The agent's polling path remains the canonical
    way to learn about completion — webhooks are a low-latency
    optimisation for durable adapters that already pay for delivery
    durability themselves (Temporal signals, LangGraph checkpoints)."""
    if not task.callback_url:
        return

    body = json.dumps(_build_payload(task), separators=(",", ":")).encode()
    headers = {
        "Content-Type": "application/json",
        WEBHOOK_SIGNATURE_HEADER: sign_body(body),
        "X-Awaithumans-Task-Id": task.id,
    }

    try:
        async with httpx.AsyncClient(
            timeout=WEBHOOK_DELIVERY_TIMEOUT_SECONDS
        ) as client:
            resp = await client.post(task.callback_url, content=body, headers=headers)
            if resp.status_code >= 400:
                logger.warning(
                    "Webhook POST returned %d for task=%s url=%s",
                    resp.status_code,
                    task.id,
                    task.callback_url,
                )
                return
            logger.info(
                "Webhook delivered task=%s url=%s status=%d",
                task.id,
                task.callback_url,
                resp.status_code,
            )
    except httpx.HTTPError as exc:
        # Connection refused, DNS failure, timeout — all expected
        # operational noise. The agent's long-poll picks up the same
        # state on the next reconnect.
        logger.warning(
            "Webhook delivery failed task=%s url=%s: %s",
            task.id,
            task.callback_url,
            exc,
        )
