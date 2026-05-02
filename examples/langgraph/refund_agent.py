"""LangGraph agent that awaits a human for a refund decision.

Pattern (vs Temporal): the graph is library-style — there's no
separate worker process. The single entry point streams the graph,
hits an interrupt when `await_human(...)` runs in a node, drives the
human-in-the-loop dance, and returns the final state.

Run:
    python refund_agent.py 250

Prerequisites:
  1. The awaithumans server is running:  `awaithumans dev`
  2. (One-time) install this example's deps:
       pip install -r examples/langgraph/requirements.txt
  3. (Optional) export AWAITHUMANS_URL + AWAITHUMANS_ADMIN_API_TOKEN
     to point at a non-default server.

The script:
  - builds a 3-node graph: triage → review (await_human) → process
  - runs `drive_human_loop`, which catches the await_human interrupt,
    creates the task on the awaithumans server, long-polls, and
    resumes the graph with the human's decision
  - prints the final state

Open the awaithumans dashboard at http://localhost:3001 while this
runs to see the task land. Submit your decision and the script
prints the result a moment later.
"""

from __future__ import annotations

import asyncio
import logging
import os
import sys
from typing import TypedDict

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph
from pydantic import BaseModel

from awaithumans.adapters.langgraph import await_human, drive_human_loop

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("examples.langgraph.refund_agent")


# ─── State + schemas ─────────────────────────────────────────────────


class State(TypedDict):
    customer_id: str
    amount_usd: int
    triage_score: float
    approved: bool
    refund_id: str | None


class RefundPayload(BaseModel):
    """What the human reviewer sees."""

    customer_id: str
    amount_usd: int
    triage_score: float
    reason: str


class RefundDecision(BaseModel):
    """What the human sends back."""

    approved: bool
    notes: str | None = None


# ─── Nodes ───────────────────────────────────────────────────────────


def triage_node(state: State) -> dict:
    """Cheap pre-check before bothering a human.

    A real implementation would call your fraud / risk model here
    and use the score to decide whether to skip the human review
    altogether (auto-approve below threshold, auto-decline above).
    For the demo we always go to the human."""
    score = 0.42 if state["amount_usd"] < 500 else 0.78
    logger.info(
        "Triage: customer=%s amount=$%d score=%.2f",
        state["customer_id"],
        state["amount_usd"],
        score,
    )
    return {"triage_score": score}


def review_node(state: State) -> dict:
    """The human-in-the-loop step.

    On first execution this hits `interrupt(...)` and the graph
    parks. The driver (`drive_human_loop`) creates the task on the
    awaithumans server, waits for the human, and resumes the graph
    with the response. On resume, this node re-runs from the top
    and `await_human` returns the validated decision instead of
    interrupting."""
    decision = await_human(
        task=f"Approve ${state['amount_usd']} refund for {state['customer_id']}?",
        payload_schema=RefundPayload,
        payload=RefundPayload(
            customer_id=state["customer_id"],
            amount_usd=state["amount_usd"],
            triage_score=state["triage_score"],
            reason="Customer reports duplicate charge.",
        ),
        response_schema=RefundDecision,
        timeout_seconds=15 * 60,
    )
    logger.info(
        "Decision received: approved=%s notes=%r",
        decision.approved,
        decision.notes,
    )
    return {"approved": decision.approved}


def process_refund_node(state: State) -> dict:
    """Stand-in for "actually move the money." A real implementation
    would call your payments provider here."""
    if not state["approved"]:
        logger.info("Refund declined — no payment action.")
        return {"refund_id": None}
    refund_id = f"refund-{state['customer_id']}-{state['amount_usd']}"
    logger.info("Processed refund: %s", refund_id)
    return {"refund_id": refund_id}


# ─── Graph wiring ────────────────────────────────────────────────────


def build_graph():
    builder = StateGraph(State)
    builder.add_node("triage", triage_node)
    builder.add_node("review", review_node)
    builder.add_node("process_refund", process_refund_node)
    builder.add_edge(START, "triage")
    builder.add_edge("triage", "review")
    builder.add_edge("review", "process_refund")
    builder.add_edge("process_refund", END)
    # `MemorySaver` is fine for a single-process demo. Production
    # graphs use SQLite / Postgres / Redis checkpointers — the
    # awaithumans adapter doesn't care which.
    return builder.compile(checkpointer=MemorySaver())


# ─── CLI entrypoint ──────────────────────────────────────────────────


async def run(amount_usd: int) -> None:
    graph = build_graph()
    config = {"configurable": {"thread_id": f"refund-cus_demo-{amount_usd}"}}

    server_url = os.environ.get("AWAITHUMANS_URL", "http://localhost:3001")
    api_key = os.environ.get("AWAITHUMANS_ADMIN_API_TOKEN")

    logger.info("Starting graph — open the dashboard at %s", server_url)
    final_state = await drive_human_loop(
        graph,
        input_state={
            "customer_id": "cus_demo",
            "amount_usd": amount_usd,
            "triage_score": 0.0,
            "approved": False,
            "refund_id": None,
        },
        config=config,
        server_url=server_url,
        api_key=api_key,
    )
    logger.info("Graph completed: %s", final_state.values)


def main() -> None:
    amount = int(sys.argv[1]) if len(sys.argv) > 1 else 100
    asyncio.run(run(amount))


if __name__ == "__main__":
    main()
