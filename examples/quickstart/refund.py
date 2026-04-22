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
    switch (toggle); `note` renders as an optional long-text field."""

    approved: bool = Field(..., description="Approve the refund?")
    note: str | None = Field(
        default=None,
        description="Optional message to send to the customer.",
    )


def main() -> None:
    print("→ creating task on the awaithumans server...")
    print("  Open http://localhost:3001 to review.\n")

    decision = await_human_sync(
        task="Approve refund request",
        payload_schema=RefundRequest,
        payload=RefundRequest(
            order_id="A-4721",
            customer="jane@example.com",
            amount_usd=180.00,
            reason="Item arrived damaged",
        ),
        response_schema=Decision,
        timeout_seconds=900,  # 15 minutes — plenty of time to walk to the kitchen
    )

    if decision.approved:
        print(f"✓ Refund approved. Note: {decision.note or '(none)'}")
    else:
        print(f"✗ Refund rejected. Note: {decision.note or '(none)'}")


if __name__ == "__main__":
    main()
