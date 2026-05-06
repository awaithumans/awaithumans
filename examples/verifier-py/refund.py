"""
awaithumans verifier example (Python) — refund approval gated by an
LLM verifier.

Scenario: the human's decision must pass an LLM quality check before
the agent unblocks. The verifier reads the original request, the
decision, and a strict policy, then either passes (→ COMPLETED) or
rejects (→ REJECTED, can resubmit; → VERIFICATION_EXHAUSTED after the
attempt limit).

Prerequisites
-------------
1. In another terminal, with `ANTHROPIC_API_KEY` exported in that
   shell so the SERVER can call Claude:

       export ANTHROPIC_API_KEY=sk-ant-...
       pip install "awaithumans[server,verifier-claude]"
       awaithumans dev

2. Then in this terminal:

       pip install -r requirements.txt
       python refund.py

What to do (manual verifier test)
---------------------------------
Open http://localhost:3001 and review the task. Try the three paths:

  Pass        — approve the refund and write a reason that mentions
                "damage" / "policy" / "evidence". Verifier passes;
                this script unblocks with the typed Decision.

  Reject+retry— write a vague reason like "ok". Verifier rejects on
                the first attempt; the dashboard shows the rejection
                reason and lets you resubmit. Up to `max_attempts`.

  Exhaust     — keep submitting bad reasons. After max_attempts the
                task transitions to VERIFICATION_EXHAUSTED (terminal)
                and this script raises VerificationExhaustedError.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from awaithumans import await_human_sync
from awaithumans.errors import VerificationExhaustedError
from awaithumans.verifiers.claude import claude_verifier


class RefundRequest(BaseModel):
    order_id: str
    customer: str
    amount_usd: float
    reason: str


class Decision(BaseModel):
    approved: bool = Field(..., description="Approve the refund?")
    reason: str = Field(
        ...,
        description=(
            "Why? If approving, mention damage / policy / evidence. "
            "If rejecting, at least 20 characters explaining why."
        ),
    )


VERIFIER_INSTRUCTIONS = """\
You are a quality gate for refund decisions. Read the original
request (in `payload`) and the human's decision (in `response`).

PASS only if BOTH hold:
  1. If `response.approved` is true, `response.reason` must mention
     at least one of: "damage", "policy", "evidence" (case-insensitive).
  2. If `response.approved` is false, `response.reason` must be at
     least 20 characters and substantively explain the rejection.

Otherwise REJECT with a short, actionable reason the human will see.
"""


def main() -> None:
    order_id = "A-9921"

    print("→ creating refund task with a Claude verifier attached...")
    print("  Open http://localhost:3001 to review.\n")

    try:
        decision = await_human_sync(
            task="Approve refund (verified)",
            payload_schema=RefundRequest,
            payload=RefundRequest(
                order_id=order_id,
                customer="riley@example.com",
                amount_usd=420.00,
                reason="Item arrived broken; customer sent two photos.",
            ),
            response_schema=Decision,
            timeout_seconds=900,
            verifier=claude_verifier(
                instructions=VERIFIER_INSTRUCTIONS,
                max_attempts=3,
            ),
            idempotency_key=f"refund-verified:{order_id}",
        )
    except VerificationExhaustedError as exc:
        print(f"✗ Verifier exhausted after {exc.attempts} attempts.")
        print("  The agent is unblocked but the task did not pass review.")
        return

    if decision.approved:
        print(f"✓ Refund approved (verifier passed). Reason: {decision.reason}")
    else:
        print(f"✗ Refund rejected (verifier passed). Reason: {decision.reason}")


if __name__ == "__main__":
    main()
