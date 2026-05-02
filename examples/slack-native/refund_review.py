"""Slack-native refund review — complete the loop without opening the dashboard.

This example shows what 'Slack-native' means: an operator never has to
leave Slack. The agent posts to a channel, anyone in the channel can
claim it, the claimer fills the form (modal) OR replies to the thread
with natural language, and the agent gets a typed decision back.

Three Slack-channel capabilities used together:

  1. Broadcast-to-channel claim — `notify=["slack:#approvals"]`
     posts a "Claim this task" button. First clicker wins atomically.
  2. Modal review — claim opens a Block Kit modal with the form,
     auto-generated from the response schema.
  3. Natural-language reply — instead of clicking through the modal,
     the reviewer can reply in the message's thread ("approve, looks
     legit") and the verifier parses it into the structured response.

Prerequisites (in three separate terminals):

  Terminal 1: the awaithumans server
      awaithumans dev

  Terminal 2: a public tunnel (so Slack can reach interactivity webhooks)
      ngrok http 3001
      # copy the https URL Slack will hit

  Terminal 3: this script
      cd examples/slack-native
      python -m venv .venv && source .venv/bin/activate
      pip install -r requirements.txt
      python refund_review.py 250

Slack app setup (one-time):
  See README.md for the full app-manifest snippet. Short version:
    - Create a Slack app at api.slack.com/apps → From manifest
    - Set the manifest's `request_url` to <ngrok-https-url>/api/channels/slack/interactions
    - Install to your workspace
    - Copy the bot token + signing secret into your awaithumans server env
    - Invite the bot to your #approvals channel

Optional but recommended:
    export ANTHROPIC_API_KEY=sk-ant-...     # for the verifier (NL parsing)

What you'll see in Slack:

    [#approvals]
    bot: 🤖 Approve $250 refund for cus_demo?
         [ Claim this task ]                              ← anyone can click
                                                            first-claim-wins

    (Alice clicks Claim)
    bot: ✓ Claimed by @alice                              ← message updates,
                                                            button vanishes

    Modal pops for Alice → form with switch + notes field.
    OR Alice replies in the thread:
       @alice: approve, looks legit — duplicate confirmed by Stripe

This script's terminal will print the typed decision a moment later.
"""

from __future__ import annotations

import logging
import os
import sys

from pydantic import BaseModel, Field

from awaithumans import await_human_sync
from awaithumans.verifiers.claude import claude_verifier

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("examples.slack_native.refund_review")


# ─── Schemas ─────────────────────────────────────────────────────────


class RefundPayload(BaseModel):
    """What the human sees — payload context in the Slack message and modal header."""

    customer_id: str = Field(description="Stripe customer ID")
    amount_usd: int = Field(description="Refund amount in USD")
    reason: str = Field(description="Why the agent flagged this for review")


class RefundDecision(BaseModel):
    """What the human sends back — drives the modal form fields.

    `approved` renders as a yes/no radio. `notes` renders as a
    multiline plain_text_input. The verifier (when an LLM key is
    configured) ALSO parses NL thread replies into this shape."""

    approved: bool = Field(description="Approve the refund?")
    notes: str | None = Field(
        default=None,
        description="Reasoning. Required for amounts over $1000.",
    )


# ─── Verifier (optional) ─────────────────────────────────────────────


def _verifier_or_none():
    """Configure the Claude verifier if an API key is around.

    The verifier does two jobs:
      - Quality-check the human's structured submission (e.g. reject
        if approved=true but notes contradict).
      - Parse natural-language thread replies into the response schema.
        This is what makes 'reply in Slack thread' work without a
        second code path.

    Without ANTHROPIC_API_KEY, we skip the verifier — the modal still
    works fine, but NL replies will arrive as raw text the agent has
    to handle itself."""
    if not os.environ.get("ANTHROPIC_API_KEY"):
        logger.info(
            "ANTHROPIC_API_KEY not set — running without verifier. "
            "Modal flow works; NL thread replies will not be parsed.",
        )
        return None
    return claude_verifier(
        instructions=(
            "You are reviewing a refund decision submitted by a human "
            "ops reviewer. Two jobs:\n"
            "\n"
            "1. QUALITY: Reject if the decision contradicts the notes "
            "(e.g. notes say 'looks fraudulent' but approved=true). "
            "For amounts over $1000, require non-empty notes "
            "explaining the rationale.\n"
            "\n"
            "2. NL PARSING: If the human replied in free text "
            "(raw_input is set), extract the decision into the schema. "
            "'approve', 'yes', 'go ahead', 'ok' → approved=true. "
            "'reject', 'no', 'denied' → approved=false. Pull the "
            "rationale into `notes`. If ambiguous, reject with: "
            "'Please reply with one of: approve, reject — and a "
            "one-sentence reason.'"
        ),
        max_attempts=3,
    )


# ─── Main ────────────────────────────────────────────────────────────


def review_refund(amount_usd: int, customer_id: str = "cus_demo") -> RefundDecision:
    """Block until a human approves or rejects this refund via Slack.

    `notify=["slack:#approvals"]` makes the bot post to that channel
    with a Claim button. First clicker wins; the modal opens for them.
    The reviewer can complete via the modal OR by replying NL in the
    thread (when the verifier is configured)."""
    return await_human_sync(
        task=f"Approve ${amount_usd} refund for {customer_id}?",
        payload_schema=RefundPayload,
        payload=RefundPayload(
            customer_id=customer_id,
            amount_usd=amount_usd,
            reason="Customer reports duplicate charge from yesterday.",
        ),
        response_schema=RefundDecision,
        timeout_seconds=15 * 60,
        notify=[
            # The channel your bot is in. Override with
            # AWAITHUMANS_DEMO_CHANNEL if you want a different one.
            f"slack:{os.environ.get('AWAITHUMANS_DEMO_CHANNEL', '#approvals')}",
        ],
        verifier=_verifier_or_none(),
        idempotency_key=f"refund-review:{customer_id}:{amount_usd}",
    )


def main() -> None:
    amount = int(sys.argv[1]) if len(sys.argv) > 1 else 250
    print(  # noqa: T201 — user-facing CLI output
        f"\n→ Posting ${amount} refund review to Slack. "
        f"Watch the channel; the bot will post a Claim button.\n"
    )

    decision = review_refund(amount)

    if decision.approved:
        print(f"\n✓ Approved. Notes: {decision.notes!r}")  # noqa: T201
        # In a real agent this is where you'd call your payments
        # provider. For the demo we just log the outcome.
    else:
        print(f"\n✗ Rejected. Notes: {decision.notes!r}")  # noqa: T201


if __name__ == "__main__":
    main()
