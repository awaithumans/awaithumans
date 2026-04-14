"""
awaithumans quickstart — minimal direct-mode example.

Prerequisites:
    pip install "awaithumans[server]"
    awaithumans dev    # in another terminal

Then run:
    python example.py
"""

from __future__ import annotations

import asyncio

from pydantic import BaseModel, Field

from awaithumans import await_human


# ── Define your schemas ──────────────────────────────────────────────────

class RefundPayload(BaseModel):
    """What the human reviewer sees."""
    amount: float = Field(description="Refund amount in dollars")
    customer: str = Field(description="Customer ID")
    reason: str = Field(description="Why the refund was requested")


class RefundDecision(BaseModel):
    """What the human reviewer submits."""
    approved: bool = Field(description="Approve this refund?")
    reviewer_note: str | None = Field(default=None, description="Optional note")


# ── Run the agent ────────────────────────────────────────────────────────

async def main() -> None:
    print("Creating a task for human review...")
    print("Open http://localhost:3001/api/tasks to see the task.")
    print("Complete it via: POST http://localhost:3001/api/tasks/{id}/complete")
    print()

    result = await await_human(
        task="Approve this refund?",
        payload_schema=RefundPayload,
        payload=RefundPayload(
            amount=240.00,
            customer="cus_123",
            reason="Product arrived damaged",
        ),
        response_schema=RefundDecision,
        timeout_seconds=300,  # 5 minutes
        notify=["slack:#ops"],  # optional — requires Slack configured
    )

    print(f"Human decided: approved={result.approved}")
    if result.reviewer_note:
        print(f"Reviewer note: {result.reviewer_note}")


if __name__ == "__main__":
    asyncio.run(main())
