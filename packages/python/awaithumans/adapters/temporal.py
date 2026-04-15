"""Temporal adapter — signal-based durable HITL.

Usage:
    from awaithumans.adapters.temporal import await_human

    # Inside a Temporal workflow:
    result = await await_human(
        task="Approve this KYC?",
        payload_schema=KYCPayload,
        payload=kycData,
        response_schema=KYCResponse,
        timeout_seconds=900,
    )

Requires: pip install "awaithumans[temporal]"
"""

from __future__ import annotations


async def await_human(**kwargs: object) -> object:
    """Temporal-durable version of await_human.

    Uses Temporal signals + sleep race for zero-compute waiting.
    """
    try:
        import temporalio  # noqa: F401
    except ImportError:
        raise ImportError(
            "The Temporal adapter requires the [temporal] extra.\n"
            'Install with: pip install "awaithumans[temporal]"'
        )

    # TODO: implement
    # 1. Create task on the awaithumans server (HTTP POST)
    # 2. Register a Temporal signal handler for task completion
    # 3. Race: workflow.wait_condition(signal_received) vs workflow.sleep(timeout)
    # 4. On signal: validate response, return typed result
    # 5. On timeout: raise TimeoutError
    # Idempotency key: workflow_info().workflow_id + activity_info().activity_id
    raise NotImplementedError("Temporal adapter not yet implemented.")
