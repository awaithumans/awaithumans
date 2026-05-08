"""Application — graph + checkpointer + HTTP surface, all in one process.

Mirrors `examples/langgraph-ts/app.ts`. ONE FastAPI process owns the
graph, the checkpointer, and the awaithumans webhook receiver. A node
calling `await_human` ↔ a webhook that comes back later ↔ a
`Command(resume=…)` invocation are all the same process, the same
compiled graph, the same checkpointer.

Two routes:

  POST /start         {customer_id, amount_usd}      → kicks off a run
                                                       returns thread id +
                                                       interrupt info
                                                       (or final state if
                                                       auto-approved)

  POST /awaithumans/cb?thread=<thread_id>             → awaithumans webhook;
                                                       resumes the graph

Run with:
    AWAITHUMANS_PAYLOAD_KEY=$(cat <discovery>/payload.key) \\
        uvicorn app:app --host 0.0.0.0 --port 8765

Then in another terminal:
    python kickoff.py 250 cus_demo
"""

from __future__ import annotations

import logging
import os
import uuid
from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel

from awaithumans.adapters.langgraph import dispatch_resume
from awaithumans.utils.discovery import resolve_admin_token, resolve_server_url

from graph import GraphConfig, build_refund_graph

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("examples.langgraph_py.app")

PORT = int(os.environ.get("PORT", "8765"))
CALLBACK_BASE = os.environ.get(
    "AWAITHUMANS_CALLBACK_BASE", f"http://localhost:{PORT}"
)


# Module-level holders. We can't construct the graph at import time
# because we need to resolve the awaithumans config asynchronously
# (discovery file lookups are async) — so the lifespan populates them.
_graph: object | None = None
_thread_id_ref: list[str] = ["<unset>"]
_payload_key: str | None = None


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    global _graph, _payload_key

    _payload_key = os.environ.get("AWAITHUMANS_PAYLOAD_KEY")
    if not _payload_key:
        raise RuntimeError(
            "AWAITHUMANS_PAYLOAD_KEY is required.\n"
            "  Dev: export AWAITHUMANS_PAYLOAD_KEY="
            "$(cat .awaithumans/payload.key) "
            "(from wherever you ran `awaithumans dev`)."
        )

    server_url = resolve_server_url()
    api_key = resolve_admin_token()
    if not api_key:
        raise RuntimeError(
            "Couldn't find an admin token. Run `awaithumans dev` "
            "(writes ~/.awaithumans-dev.json) or export "
            "AWAITHUMANS_ADMIN_API_TOKEN."
        )

    cfg = GraphConfig(
        awaithumans_server_url=server_url,
        awaithumans_api_key=api_key,
        callback_base=CALLBACK_BASE,
        auto_approve_threshold_usd=100.0,
        # Demo convenience: pre-assign tasks to the operator who'll
        # approve them in the dashboard, so the response form
        # renders without needing a Claim flow. Leave unset in
        # production; operators claim from the dashboard once that
        # button ships.
        assign_to_email=os.environ.get("AWAITHUMANS_DEMO_ASSIGN_TO") or None,
    )
    _graph = build_refund_graph(cfg, _thread_id_ref)
    logger.info("[app] graph + callback at http://localhost:%s", PORT)
    logger.info("[app] awaithumans server: %s", server_url)
    logger.info("[app] callback base: %s", CALLBACK_BASE)
    if cfg.assign_to_email:
        logger.info(
            "[app] tasks will be assigned to %s (AWAITHUMANS_DEMO_ASSIGN_TO)",
            cfg.assign_to_email,
        )
    yield


app = FastAPI(lifespan=lifespan)


class StartRequest(BaseModel):
    customer_id: str
    amount_usd: float


@app.post("/start")
async def start(req: StartRequest) -> dict:
    """Kicks off a refund run. Returns either the final state (if
    auto-approved) or the interrupt payload (if a human is needed)."""
    if _graph is None:
        raise HTTPException(status_code=503, detail="Graph not ready.")

    thread_id = f"refund-{uuid.uuid4()}"
    _thread_id_ref[0] = thread_id

    config = {"configurable": {"thread_id": thread_id}}
    initial_state = {"customer_id": req.customer_id, "amount_usd": req.amount_usd}
    result = await _graph.ainvoke(initial_state, config=config)

    # Same shape as the TS example: `.ainvoke()` returns the committed
    # state values, NOT a `__interrupt__` field. To know if we paused,
    # ask the checkpointer via `aget_state`.
    state = await _graph.aget_state(config)
    interrupts: list[object] = []
    for task in state.tasks:
        interrupts.extend(task.interrupts or [])

    if interrupts:
        logger.info("[start] graph paused thread=%s", thread_id)
        return {
            "thread_id": thread_id,
            "status": "interrupted",
            # Pydantic-friendly serialisation of the Interrupt objects.
            "interrupts": [
                {
                    "value": getattr(i, "value", None),
                    "ns": list(getattr(i, "ns", []) or []),
                    "resumable": getattr(i, "resumable", True),
                }
                for i in interrupts
            ],
        }

    logger.info(
        "[start] graph finished thread=%s approved=%s",
        thread_id,
        result.get("approved"),
    )
    return {"thread_id": thread_id, "status": "completed", "state": result}


@app.post("/awaithumans/cb")
async def awaithumans_callback(request: Request, thread: str) -> dict:
    """Receives the awaithumans webhook. Verifies HMAC, resumes graph."""
    if _graph is None or _payload_key is None:
        raise HTTPException(status_code=503, detail="Graph not ready.")

    body = await request.body()
    signature = request.headers.get("x-awaithumans-signature")

    # Setting the ref BEFORE the resume isn't strictly needed — after
    # this resume the human_review node won't run again on this
    # thread. But if the graph had MULTIPLE interrupts on the same
    # thread, the next one would need this set.
    _thread_id_ref[0] = thread

    try:
        await dispatch_resume(
            graph=_graph,
            thread_id=thread,
            body=body,
            signature_header=signature,
        )
    except PermissionError as exc:
        logger.warning("Rejected webhook with bad signature: %s", exc)
        raise HTTPException(status_code=401, detail=str(exc)) from exc
    except ValueError as exc:
        logger.warning("Rejected malformed webhook: %s", exc)
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    logger.info("[cb] thread=%s resumed", thread)

    state = await _graph.aget_state({"configurable": {"thread_id": thread}})
    return {"ok": True, "state": state.values}


@app.get("/threads/{thread_id}")
async def get_thread(thread_id: str) -> dict:
    """Lets the kickoff client poll for completion."""
    if _graph is None:
        raise HTTPException(status_code=503, detail="Graph not ready.")
    state = await _graph.aget_state({"configurable": {"thread_id": thread_id}})
    interrupts: list[object] = []
    for task in state.tasks:
        interrupts.extend(task.interrupts or [])
    return {
        "thread_id": thread_id,
        "values": state.values,
        "interrupts": [
            {"value": getattr(i, "value", None)} for i in interrupts
        ],
    }
