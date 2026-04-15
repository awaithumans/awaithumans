"""LangGraph adapter — interrupt/resume durable HITL.

Usage:
    from awaithumans.adapters.langgraph import await_human

    # Inside a LangGraph node:
    result = await await_human(
        task="Approve this KYC?",
        payload_schema=KYCPayload,
        payload=kycData,
        response_schema=KYCResponse,
        timeout_seconds=900,
    )

Requires: pip install "awaithumans[langgraph]"
"""

from __future__ import annotations


async def await_human(**kwargs: object) -> object:
    """LangGraph-durable version of await_human.

    Uses LangGraph interrupt/resume with checkpoint-based durability.
    """
    try:
        import langgraph  # noqa: F401
    except ImportError:
        raise ImportError(
            "The LangGraph adapter requires the [langgraph] extra.\n"
            'Install with: pip install "awaithumans[langgraph]"'
        )

    # TODO: implement
    # 1. Create task on the awaithumans server (HTTP POST)
    # 2. Use langgraph interrupt(task_id) to suspend the graph
    # 3. Server fires webhook on completion → callback handler resumes graph
    # 4. Validate response, return typed result
    # Idempotency key: thread_id + node_id from checkpoint
    raise NotImplementedError("LangGraph adapter not yet implemented.")
