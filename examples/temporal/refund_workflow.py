"""Temporal workflow that awaits a human for a refund decision.

Pattern:

  - The workflow `RefundWorkflow.run(amount)` calls `await_human()`
    which suspends the workflow until either:
      * the human submits a decision via the awaithumans dashboard /
        Slack / email, OR
      * the timeout fires (here: 15 minutes)
  - On approval, the workflow calls a downstream activity
    (`process_refund`) to actually move the money.
  - On rejection, it logs the outcome and ends the workflow.
  - On timeout, it raises so the operator's monitoring catches the
    abandoned approval.

To run end-to-end you need three processes:
  1. The awaithumans server     — `awaithumans dev`
  2. THIS Temporal worker        — `python refund_workflow.py worker`
  3. The callback web server     — `python callback_server.py`
  4. (One-shot kickoff)          — `python refund_workflow.py start 250`

Env vars:
  - AWAITHUMANS_URL                   default: http://localhost:3001
  - AWAITHUMANS_ADMIN_API_TOKEN       (read from ~/.awaithumans-dev.json
                                        in dev mode, otherwise required)
  - AWAITHUMANS_CALLBACK_BASE         default: http://localhost:8765
                                        — must point at callback_server.py
                                        from a place the awaithumans
                                        server can reach. For local dev
                                        use ngrok or a similar tunnel.
"""

from __future__ import annotations

import asyncio
import logging
import os
import sys
import uuid
from dataclasses import dataclass
from datetime import timedelta

from pydantic import BaseModel
from temporalio import activity, workflow
from temporalio.client import Client
from temporalio.worker import Worker

# Sandbox-safe import: anything that triggers the Temporal sandbox
# guard (e.g. heavy modules) goes inside `unsafe.imports_passed_through`.
with workflow.unsafe.imports_passed_through():
    from awaithumans.adapters.temporal import await_human

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("examples.temporal.refund_workflow")

TASK_QUEUE = "awaithumans-refunds"


# ─── Pydantic schemas ─────────────────────────────────────────────────


class RefundPayload(BaseModel):
    """What the human reviewer sees."""

    amount_usd: int
    customer_id: str
    reason: str


class RefundDecision(BaseModel):
    """What the human sends back."""

    approved: bool
    notes: str | None = None


# ─── Downstream activity (fires after the human decides) ─────────────


@dataclass
class ProcessRefundInput:
    customer_id: str
    amount_usd: int
    decision_notes: str | None


@activity.defn
async def process_refund(req: ProcessRefundInput) -> str:
    """Stand-in for "actually move the money."

    A real implementation would call your payments provider here.
    Activities can do arbitrary I/O — they're not subject to the
    workflow determinism constraints."""
    logger.info(
        "Processing refund for customer=%s amount=$%d notes=%r",
        req.customer_id,
        req.amount_usd,
        req.decision_notes,
    )
    return f"refund-{uuid.uuid4()}"


# ─── Workflow ────────────────────────────────────────────────────────


@workflow.defn
class RefundWorkflow:
    @workflow.run
    async def run(self, amount: int, customer_id: str = "cus_demo") -> dict:
        # Block for up to 15 minutes waiting for the human.
        decision = await await_human(
            task=f"Approve ${amount} refund for {customer_id}?",
            payload_schema=RefundPayload,
            payload=RefundPayload(
                amount_usd=amount,
                customer_id=customer_id,
                reason="Customer reports duplicate charge.",
            ),
            response_schema=RefundDecision,
            timeout_seconds=15 * 60,
            callback_url=_callback_url_for_workflow(workflow.info().workflow_id),
            server_url=os.environ.get("AWAITHUMANS_URL", "http://localhost:3001"),
            api_key=os.environ.get("AWAITHUMANS_ADMIN_API_TOKEN"),
        )

        if not decision.approved:
            return {"refund_id": None, "outcome": "rejected", "notes": decision.notes}

        refund_id = await workflow.execute_activity(
            process_refund,
            ProcessRefundInput(
                customer_id=customer_id,
                amount_usd=amount,
                decision_notes=decision.notes,
            ),
            start_to_close_timeout=timedelta(seconds=30),
        )
        return {"refund_id": refund_id, "outcome": "approved", "notes": decision.notes}


def _callback_url_for_workflow(workflow_id: str) -> str:
    """Build the webhook URL for THIS workflow.

    `callback_server.py` reads the `wf` query param to know which
    workflow to signal. The full URL must be reachable from wherever
    the awaithumans server is running — for local dev with ngrok
    tunnel, override AWAITHUMANS_CALLBACK_BASE."""
    base = os.environ.get("AWAITHUMANS_CALLBACK_BASE", "http://localhost:8765")
    return f"{base.rstrip('/')}/awaithumans/callback?wf={workflow_id}"


# ─── Worker boot + one-shot kickoff (CLI entrypoints) ────────────────


async def run_worker() -> None:
    client = await Client.connect("localhost:7233")
    async with Worker(
        client,
        task_queue=TASK_QUEUE,
        workflows=[RefundWorkflow],
        activities=[process_refund],
    ):
        logger.info("Worker started — task queue=%s", TASK_QUEUE)
        # Block forever; ctrl-C exits.
        await asyncio.Event().wait()


async def kickoff(amount: int) -> None:
    client = await Client.connect("localhost:7233")
    workflow_id = f"refund-{uuid.uuid4()}"
    handle = await client.start_workflow(
        RefundWorkflow.run,
        amount,
        id=workflow_id,
        task_queue=TASK_QUEUE,
    )
    logger.info("Started workflow id=%s — waiting for human via dashboard", workflow_id)
    result = await handle.result()
    logger.info("Workflow result: %s", result)


def main() -> None:
    if len(sys.argv) < 2:
        print(__doc__, file=sys.stderr)
        sys.exit(1)
    cmd = sys.argv[1]
    if cmd == "worker":
        asyncio.run(run_worker())
    elif cmd == "start":
        amount = int(sys.argv[2]) if len(sys.argv) > 2 else 100
        asyncio.run(kickoff(amount))
    else:
        print(f"Unknown command: {cmd}", file=sys.stderr)
        print(__doc__, file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
