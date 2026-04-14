"""
awaithumans — The human layer for AI agents.

Your agents already await promises. Now they can await humans.

Usage (async):
    from awaithumans import await_human

    result = await await_human(
        task="Approve this refund?",
        payload_schema=RefundPayload,
        payload=RefundPayload(amount=240, customer="cus_123"),
        response_schema=RefundDecision,
        timeout_seconds=900,
    )

Usage (sync):
    from awaithumans import await_human_sync

    result = await_human_sync(task=..., ...)
"""

__version__ = "0.1.0"

from awaithumans.client import await_human, await_human_sync
from awaithumans.types import (
    AssignTo,
    AwaitHumanOptions,
    HumanIdentity,
    TaskRecord,
    TaskStatus,
    VerificationContext,
    VerifierConfig,
    VerifierResult,
)
from __future__ import annotations

from awaithumans.errors import (
    AwaitHumansError,
    MarketplaceNotAvailableError,
    SchemaValidationError,
    TaskAlreadyTerminalError,
    TaskTimeoutError,
    TimeoutRangeError,
    VerificationExhaustedError,
)

__all__ = [
    "await_human",
    "await_human_sync",
    "AssignTo",
    "AwaitHumanOptions",
    "HumanIdentity",
    "TaskRecord",
    "TaskStatus",
    "VerificationContext",
    "VerifierConfig",
    "VerifierResult",
    "AwaitHumansError",
    "MarketplaceNotAvailableError",
    "SchemaValidationError",
    "TaskAlreadyTerminalError",
    "TaskTimeoutError",
    "TimeoutRangeError",
    "VerificationExhaustedError",
]
