"""Refund-approval graph — three nodes, one human-in-the-loop interrupt.

The shape:

    [start] → check_policy → (auto_approve) → end
                          ↘ human_review ↗
                            (calls await_human)
                            (graph pauses here on first run;
                             resumes from the same line on Command(resume))

`await_human` from `awaithumans.adapters.langgraph` is a single
function call inside `human_review`. When it runs the first time, it
POSTs the task to the awaithumans server and then calls LangGraph's
`interrupt(...)`. That throws a GraphInterrupt — `graph.ainvoke()`
returns to the caller (our app.py) and the application returns to
its event loop. Later, when the awaithumans webhook fires, the
callback handler re-invokes the graph with `Command(resume=…)`, the
node replays, and the SAME `await await_human(...)` line returns
the validated decision.

That's the whole story: one function, two phases, durable in
between because LangGraph's checkpointer holds the state.
"""

from __future__ import annotations

import logging
from typing import Annotated, TypedDict

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph
from pydantic import BaseModel

from awaithumans.adapters.langgraph import await_human

logger = logging.getLogger("examples.langgraph_py.graph")


# ─── State ──────────────────────────────────────────────────────────


class RefundState(TypedDict, total=False):
    """LangGraph state — keys merged across nodes (latest write wins).

    `total=False` so partial updates are valid; the type checker
    won't complain when a node only sets a few fields."""

    customer_id: str
    amount_usd: float
    auto_approved: bool
    approved: bool
    notes: str


# ─── Schemas (shared between adapter call + UI rendering) ──────────


class RefundPayload(BaseModel):
    customer_id: str
    amount_usd: float
    reason: str


class RefundResponse(BaseModel):
    approved: bool
    notes: str = ""


# ─── Build-time config ─────────────────────────────────────────────


class GraphConfig(BaseModel):
    """Everything the nodes need that's NOT part of the per-run state.

    Captured by closures inside `build_refund_graph` so node functions
    don't have to thread it through the LangGraph runtime config."""

    awaithumans_server_url: str
    awaithumans_api_key: str
    callback_base: str          # e.g. "http://localhost:8765"
    auto_approve_threshold_usd: float

    # Optional: assign every human-review task to this email on
    # creation. Leaving this unset creates unassigned tasks, which is
    # fine in production (operators claim from the dashboard) but
    # awkward in the demo because the dashboard has no Claim button
    # YET — see https://github.com/awaithumans/awaithumans/issues/...
    # The cleanest demo-time fix is to assign tasks to whichever
    # operator email is logged into the dashboard so the response form
    # renders immediately.
    assign_to_email: str | None = None


# ─── Nodes ─────────────────────────────────────────────────────────


def _make_check_policy(cfg: GraphConfig):
    async def check_policy(state: RefundState) -> RefundState:
        # Trivial policy: under threshold = auto-approve. Real systems
        # would do KYC, fraud-score, etc. — the point is just to show
        # that NOT every path goes through the human.
        amount = state.get("amount_usd", 0.0)
        auto = amount < cfg.auto_approve_threshold_usd
        logger.info(
            "[node:check_policy] amount=$%s threshold=$%s → auto=%s",
            amount,
            cfg.auto_approve_threshold_usd,
            auto,
        )
        return {"auto_approved": auto}

    return check_policy


def _make_human_review(cfg: GraphConfig, thread_id_ref: list[str]):
    """Closure-bound node — `thread_id_ref[0]` is updated by app.py
    before each `.ainvoke()` so the node knows which thread it's on.

    A more idiomatic approach would thread `RunnableConfig` through
    the node signature; keeping this simple for the example."""

    async def human_review(state: RefundState) -> RefundState:
        thread_id = thread_id_ref[0]
        callback_url = (
            f"{cfg.callback_base.rstrip('/')}/awaithumans/cb?thread={thread_id}"
        )

        # THIS is the line. First run: throws GraphInterrupt; graph
        # pauses. Caller catches at .ainvoke() boundary and returns
        # to the user. On resume (graph re-invoked with
        # Command(resume=…)), the same call returns the validated
        # decision.
        #
        # idempotency_key is thread-scoped so two graph runs with
        # identical payload don't collide on the awaithumans server's
        # per-key uniqueness. Without this, replaying the demo a
        # second time would get back the FIRST run's task (with a
        # stale callback_url) and the webhook would resume the wrong
        # thread.
        decision = await await_human(
            task=f"Approve ${state['amount_usd']} refund "
                 f"for {state['customer_id']}?",
            payload_schema=RefundPayload,
            payload=RefundPayload(
                customer_id=state["customer_id"],
                amount_usd=state["amount_usd"],
                reason="Customer reports duplicate charge.",
            ),
            response_schema=RefundResponse,
            timeout_seconds=15 * 60,
            callback_url=callback_url,
            server_url=cfg.awaithumans_server_url,
            api_key=cfg.awaithumans_api_key,
            idempotency_key=f"langgraph:{thread_id}:human_review",
            # See `GraphConfig.assign_to_email` — None in production.
            assign_to=cfg.assign_to_email,
        )

        logger.info(
            "[node:human_review] decision approved=%s notes=%s",
            decision.approved,
            decision.notes or "—",
        )
        return {"approved": decision.approved, "notes": decision.notes}

    return human_review


async def auto_approve(state: RefundState) -> RefundState:
    logger.info("[node:auto_approve] $%s → approved", state["amount_usd"])
    return {"approved": True, "notes": "auto-approved (under threshold)"}


# ─── Graph factory ─────────────────────────────────────────────────


def build_refund_graph(cfg: GraphConfig, thread_id_ref: list[str]):
    """Build a compiled graph wired to a `MemorySaver` checkpointer.

    Returns the compiled graph object. The caller (app.py) holds it
    for the lifetime of the process — both `/start` (kick off) and
    `/awaithumans/cb` (resume) invoke this same compiled graph against
    different thread ids.
    """
    builder = (
        StateGraph(RefundState)
        .add_node("check_policy", _make_check_policy(cfg))
        .add_node("human_review", _make_human_review(cfg, thread_id_ref))
        .add_node("auto_approve", auto_approve)
        .add_edge(START, "check_policy")
        .add_conditional_edges(
            "check_policy",
            lambda state: "auto_approve" if state.get("auto_approved") else "human_review",
        )
        .add_edge("auto_approve", END)
        .add_edge("human_review", END)
    )
    # MemorySaver = process-local checkpointer. Fine for the demo;
    # production should swap for `langgraph.checkpoint.sqlite.SqliteSaver`
    # so the state survives restarts of the app process.
    return builder.compile(checkpointer=MemorySaver())
