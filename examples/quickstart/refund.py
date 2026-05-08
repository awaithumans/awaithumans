"""
awaithumans quickstart — delegate a refund approval to a human.

Prerequisite (in another terminal):
    pip install "awaithumans[server]"
    awaithumans dev

Then:
    python refund.py

What happens:
    1. This script creates a task on the server and blocks until
       a human completes it.
    2. Open http://localhost:3001 — the task shows up in the queue
       with an approve/reject form.
    3. Submit your decision. This script receives the typed response
       and prints it. That's it.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from awaithumans import await_human_sync


class RefundRequest(BaseModel):
    """Data the human sees while reviewing."""

    order_id: str
    customer: str
    amount_usd: float
    reason: str


class Decision(BaseModel):
    """Structured response the human fills out. `approved` drives a
    switch (toggle); `reason` renders as a short-answer text field."""

    approved: bool = Field(..., description="Approve the refund?")
    reason: str = Field(
        ...,
        description="Why did you approve / reject? Short answer.",
    )


def main() -> None:
    print("→ creating task on the awaithumans server...")
    print("  Open http://localhost:3001 to review.\n")

    order_id = "A-4721"

    decision = await_human_sync(
        task="Approve refund request",
        payload_schema=RefundRequest,
        payload=RefundRequest(
            order_id=order_id,
            customer="jane@example.com",
            amount_usd=180.00,
            reason="Item arrived damaged",
        ),
        response_schema=Decision,
        timeout_seconds=900,  # 15 minutes — plenty of time to walk to the kitchen
        # Ties this call to the order. Same key, same task — forever.
        # If the agent crashes mid-call and the human approves during
        # the outage, re-running with the same key returns the stored
        # decision (this `if decision.approved:` block runs as if
        # nothing happened). Without an explicit key the SDK
        # auto-hashes (task, payload) — fine for dev, but tie to your
        # real business event (order_id, transfer_id, request_id) in
        # production. To start a fresh review for the same event
        # (e.g. yesterday's task timed out), use a distinct key like
        # f"refund:{order_id}:retry-1".
        idempotency_key=f"refund:{order_id}",
    )

    if decision.approved:
        print(f"✓ Refund approved. Reason: {decision.reason}")
    else:
        print(f"✗ Refund rejected. Reason: {decision.reason}")


if __name__ == "__main__":
    main()
