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
import logging

from pydantic import BaseModel, Field

from awaithumans import await_human
from awaithumans.utils.discovery import resolve_server_url


# Enable INFO logging so we see task IDs as they're created.
logging.basicConfig(level=logging.INFO, format="%(message)s")


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
    server_url = resolve_server_url()
    print(f"→ Using server: {server_url}")
    print("  (auto-discovered via ~/.awaithumans-dev.json)")
    print()
    print("Creating a task for human review...")

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
        notify=["slack:#ops"],
    )

    print()
    print(f"→ Human decided: approved={result.approved}")
    if result.reviewer_note:
        print(f"  Reviewer note: {result.reviewer_note}")


if __name__ == "__main__":
    asyncio.run(main())
