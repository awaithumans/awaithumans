"""Verifier integration helpers for the task-completion path.

Lives next to `task_service` rather than inside it because the verifier
glue (build context, decide target status, derive audit label, redact
when asked) easily doubles the size of `complete_task` and isn't part
of its core business logic. Keeping it here keeps `task_service.py`
under the 300-line cap and makes the verifier path easy to swap out
when the channel layer eventually adds deferred-ack execution.

Public surface:
  - `VerifierOutcome`           — the decided fate of one attempt
  - `evaluate_submission()`     — run the verifier, pick a target status
  - `previous_rejections_for()` — prior rejection reasons for the prompt
  - `audit_action_for()`        — audit label matching the outcome

`evaluate_submission` is the only async function. It is called by
`task_service.complete_task` when `task.verifier_config` is set; the
caller passes the already-loaded `Task` row plus the raw submission
payload. We deliberately do NOT take an AsyncSession — the caller is
responsible for releasing the session before awaiting our LLM call,
otherwise the connection pool exhausts under load."""

from __future__ import annotations

import logging
from typing import Any

from pydantic import ValidationError

from awaithumans.server.db.models import Task
from awaithumans.server.services.exceptions import (
    ServiceError,
    VerifierConfigInvalidError,
)
from awaithumans.server.verification import run_verifier
from awaithumans.types import (
    TaskStatus,
    VerificationContext,
    VerifierConfig,
    VerifierResult,
)

logger = logging.getLogger("awaithumans.server.services.task_verifier")


class VerifierOutcome:
    """The decided fate of one verification attempt.

    Bundles together the verifier's verdict, the bumped attempt
    counter, the resulting target status, and (for NL paths) the
    parsed response value the caller should store on the task."""

    __slots__ = ("result", "new_attempt", "target_status", "parsed_response")

    def __init__(
        self,
        result: VerifierResult,
        new_attempt: int,
        target_status: TaskStatus,
        parsed_response: Any,
    ) -> None:
        self.result = result
        self.new_attempt = new_attempt
        self.target_status = target_status
        self.parsed_response = parsed_response


async def evaluate_submission(
    task: Task, *, response: dict, raw_input: str | None
) -> VerifierOutcome:
    """Run the configured verifier and decide the resulting state.

    Returns a `VerifierOutcome` carrying the verdict, attempt counter,
    target TaskStatus, and (when NL-parsed) the structured response
    value. The caller is responsible for the atomic UPDATE that
    persists the new state.

    Provider failures (missing API key, vendor outage, missing SDK
    extra, malformed config) propagate as ServiceError subclasses —
    those do NOT burn an attempt because the LLM never rendered a
    verdict. Only a real `passed=False` verdict counts toward
    `max_attempts`.

    `task.redact_payload=True` is honoured: the verifier is skipped
    entirely and the submission is treated as if no verifier were
    configured. We don't ship redacted-task payloads to a third-party
    LLM under any circumstance — that would silently violate the
    operator's explicit redaction request."""
    try:
        config = VerifierConfig(**(task.verifier_config or {}))
    except ValidationError as exc:
        # Surfaced through the central handler with a clear error_code
        # + docs link so operators know what to fix in the agent code,
        # not a generic 500. Common cause: bumping VerifierConfig fields
        # while old tasks still carry the old shape on disk.
        raise VerifierConfigInvalidError(str(exc)) from exc

    ctx = VerificationContext(
        task=task.task,
        payload=task.payload,
        payload_schema=task.payload_schema,
        response=response if not raw_input else None,
        response_schema=task.response_schema,
        raw_input=raw_input,
        attempt=task.verification_attempt,
        previous_rejections=previous_rejections_for(task),
    )

    try:
        result = await run_verifier(config, ctx)
    except ServiceError:
        # Typed provider/config error — re-raise so the central handler
        # turns it into a 5xx with error_code + docs_url. Don't bump
        # the attempt counter.
        raise

    new_attempt = task.verification_attempt + 1

    if result.passed:
        target = TaskStatus.COMPLETED
    elif new_attempt >= config.max_attempts:
        target = TaskStatus.VERIFICATION_EXHAUSTED
    else:
        target = TaskStatus.REJECTED

    parsed = result.parsed_response if (result.passed and raw_input) else None

    # Reason is operator-controlled LLM output and may quote payload
    # back at us. Log at DEBUG so it doesn't end up in dev-mode stdout
    # or default-config production logs by default.
    logger.info(
        "Verifier outcome task_id=%s passed=%s attempt=%d/%d → status=%s",
        task.id,
        result.passed,
        new_attempt,
        config.max_attempts,
        target.value,
    )
    logger.debug("Verifier reason task_id=%s reason=%r", task.id, result.reason)

    return VerifierOutcome(
        result=result,
        new_attempt=new_attempt,
        target_status=target,
        parsed_response=parsed,
    )


def previous_rejections_for(task: Task) -> list[str]:
    """Reasons from prior rejections, for the verifier prompt.

    For now we only carry the most recent rejection reason — the audit
    trail has the rest if a future iteration wants the full history.
    Empty list when this is the first attempt or the prior verdict
    actually passed (status wouldn't be REJECTED in that case anyway)."""
    if not task.verifier_result:
        return []
    if task.status != TaskStatus.REJECTED:
        return []
    reason = task.verifier_result.get("reason")
    return [reason] if isinstance(reason, str) and reason else []


def audit_action_for(status: TaskStatus, outcome: VerifierOutcome | None) -> str:
    """Pick the audit action label that matches the actual outcome.

    When verifier wasn't configured, this is just 'completed' as
    before. With verifier: 'verified' on pass, 'rejected' on retryable
    failure, 'verification_exhausted' on terminal failure. Distinct
    labels make the audit page readable without joining against
    verifier_result."""
    if outcome is None:
        return "completed"
    if status == TaskStatus.COMPLETED:
        return "verified"
    if status == TaskStatus.VERIFICATION_EXHAUSTED:
        return "verification_exhausted"
    return "rejected"
