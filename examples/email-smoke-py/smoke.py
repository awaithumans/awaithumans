"""End-to-end email-channel smoke test (Python).

Mirror of `examples/email-smoke/smoke.ts` — exercises the same loop
(create task with email notify → capture rendered email → click
magic link → assert agent receives the response) but driven from the
Python SDK so we have parity coverage in both languages.

What runs:

  1. Configure an email sender identity that uses the `file` transport
     (drops one JSON per email into a tmp dir).
  2. Call `await_human` with a single-boolean response schema and
     `notify=["email+<id>:..."]`. The Python SDK's `extract_form`
     produces a Switch primitive, which is what triggers the email
     renderer's magic-link path.
  3. Concurrently poll the tmp dir for the rendered email, parse out
     the Approve magic-link URL, then POST to it.
  4. Wait for `await_human` to resolve. Assert `approved is True`.

Prerequisites (in another terminal):

    awaithumans dev

Then in this terminal:

    cd examples/email-smoke-py
    pip install -r requirements.txt
    export AWAITHUMANS_ADMIN_API_TOKEN="$(cat ~/.awaithumans/admin.token)"
    python smoke.py

The script reads `AWAITHUMANS_URL` (default http://localhost:3001)
and `AWAITHUMANS_ADMIN_API_TOKEN` (required) from the env.
"""

from __future__ import annotations

import asyncio
import json
import os
import re
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

import httpx
from pydantic import BaseModel, Field

from awaithumans import await_human
from awaithumans.utils.discovery import resolve_admin_token, resolve_server_url

# ─── Config ────────────────────────────────────────────────────────────

# Resolve URL + admin token via the same chain `await_human` itself
# uses internally — explicit env var → discovery file written by
# `awaithumans dev`. Means the smoke "just works" against a running
# dev server with no env-var dance, mirroring the Python SDK's
# default DX.
SERVER_URL = resolve_server_url().rstrip("/")
ADMIN_TOKEN = resolve_admin_token()

if not ADMIN_TOKEN:
    print(
        "Couldn't find an admin token. Either:\n"
        "  - Run `awaithumans dev` (writes ~/.awaithumans-dev.json) and try again, OR\n"
        "  - Export AWAITHUMANS_ADMIN_API_TOKEN with the token your server uses.",
        file=sys.stderr,
    )
    sys.exit(1)

RECIPIENT_EMAIL = "smoke-recipient@example.test"
IDENTITY_ID = f"smoke-py-{int(time.time())}"

# Unique per-run tmp dir so old smoke runs don't pollute the magic-link
# search. Slow filesystems would still see "ls then read" race; the
# poller below tolerates it.
EMAIL_DIR = Path(tempfile.mkdtemp(prefix="awaithumans-py-smoke-"))
print(f"→ email capture dir: {EMAIL_DIR}")


# ─── Schemas ───────────────────────────────────────────────────────────


class TransferRequest(BaseModel):
    transfer_id: str = Field(...)
    amount_usd: float
    to: str


class ApprovalResponse(BaseModel):
    """Single boolean → server-side `extract_form` produces a Switch
    primitive, which is what the email renderer uses to decide whether
    to emit Approve/Reject magic-link buttons."""

    approved: bool = Field(..., description="Approve this transfer?")


# ─── Admin helpers ─────────────────────────────────────────────────────


_admin = httpx.Client(
    base_url=SERVER_URL,
    headers={
        "Authorization": f"Bearer {ADMIN_TOKEN}",
        "Content-Type": "application/json",
    },
    timeout=10,
)


def configure_file_transport_identity() -> None:
    resp = _admin.post(
        "/api/channels/email/identities",
        json={
            "id": IDENTITY_ID,
            "display_name": "Smoke test sender",
            "from_email": "smoke@app.example",
            "from_name": "awaithumans py smoke",
            "reply_to": None,
            "transport": "file",
            "transport_config": {"dir": str(EMAIL_DIR)},
        },
    )
    if resp.status_code >= 400:
        raise RuntimeError(
            f"identity create failed: {resp.status_code} {resp.text}"
        )
    print(f"→ created email identity '{IDENTITY_ID}' (file transport)")


def delete_identity() -> None:
    """Best-effort cleanup so a half-run smoke doesn't leave junk in
    the operator's identity list."""
    try:
        _admin.delete(f"/api/channels/email/identities/{IDENTITY_ID}")
    except Exception:  # noqa: BLE001
        # Non-fatal — operator can clear it manually if they care.
        pass


# ─── Magic-link capture ────────────────────────────────────────────────


_ACTION_PATH_RE = re.compile(
    r"/api/channels/email/action/[A-Za-z0-9_\-.]+"
)


async def poll_for_email(deadline: float) -> dict[str, Any]:
    while time.time() < deadline:
        files = sorted(EMAIL_DIR.glob("*.json"))
        for f in files:
            payload = json.loads(f.read_text())
            if payload.get("to") == RECIPIENT_EMAIL:
                return payload
        await asyncio.sleep(0.25)
    raise TimeoutError(
        f"Timed out waiting for email to {RECIPIENT_EMAIL} in {EMAIL_DIR}"
    )


def find_approve_link(email: dict[str, Any]) -> str:
    body_html = email.get("html", "") or ""
    body_text = email.get("text", "") or ""
    match = _ACTION_PATH_RE.search(body_text) or _ACTION_PATH_RE.search(body_html)
    if match is None:
        raise RuntimeError(
            "No magic-link URL found. Was form_definition synthesized? "
            "See packages/python/awaithumans/forms/extract.py.\n"
            f"text body:\n{body_text}\n\nhtml body:\n{body_html}"
        )
    return f"{SERVER_URL}{match.group(0)}"


def click_magic_link(url: str) -> None:
    """Public action endpoint — POST with no body completes the task."""
    resp = httpx.post(url, timeout=10)
    if resp.status_code >= 400:
        raise RuntimeError(
            f"Magic-link POST returned {resp.status_code}: {resp.text}"
        )
    print(f"→ POSTed magic-link → {resp.status_code}")


def assert_email_looks_right(email: dict[str, Any]) -> None:
    if not email.get("subject"):
        raise AssertionError("Email has empty subject")
    html = email.get("html", "")
    if "Approve wire transfer (smoke test)" not in html:
        raise AssertionError("Email body missing the task title")
    if "WT-PYSMOKE-1" not in html:
        raise AssertionError("Email body missing the payload (transfer_id)")


# ─── Orchestration ─────────────────────────────────────────────────────


async def main() -> None:
    print(f"→ smoke against {SERVER_URL}")

    configure_file_transport_identity()

    # `await_human` is awaitable; run it concurrently with the email-
    # capture poll so we can click the magic link while the SDK is
    # still polling.
    agent_task = asyncio.create_task(
        await_human(
            task="Approve wire transfer (smoke test)",
            payload_schema=TransferRequest,
            payload=TransferRequest(
                transfer_id="WT-PYSMOKE-1",
                amount_usd=10_000,
                to="Acme Inc.",
            ),
            response_schema=ApprovalResponse,
            timeout_seconds=300,  # 5 min, plenty of slack
            idempotency_key=f"email-smoke-py-{int(time.time())}",
            notify=[f"email+{IDENTITY_ID}:{RECIPIENT_EMAIL}"],
        )
    )

    # 30s deadline — the notifier runs as a background task after the
    # create-task response, so it always lands within ~1s on a healthy
    # box. 30s is paranoid.
    deadline = time.time() + 30
    email = await poll_for_email(deadline)
    print(f"→ captured email: subject=\"{email['subject']}\" to={email['to']}")
    assert_email_looks_right(email)
    print("→ email body content checks: OK")

    approve_url = find_approve_link(email)
    print(f"→ magic-link URL: {approve_url}")

    click_magic_link(approve_url)

    decision: ApprovalResponse = await agent_task
    if decision.approved is not True:
        raise AssertionError(
            f"Expected approved=True, got: {decision.model_dump()}"
        )

    print("✓ smoke pass: Python SDK + email channel + magic-link round-trip")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    finally:
        delete_identity()
        _admin.close()
