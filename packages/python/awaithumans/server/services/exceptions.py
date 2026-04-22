"""Service-layer exceptions.

All service exceptions inherit from ServiceError, which carries a status_code
and error_code. The single exception handler in core/exceptions.py uses these
to build the HTTP response — no per-exception handler functions needed.
"""

from __future__ import annotations

from awaithumans.types import TaskStatus
from awaithumans.utils.constants import DOCS_TROUBLESHOOTING_URL


class ServiceError(Exception):
    """Base exception for all service-layer errors.

    Carries status_code and error_code so the exception handler can build
    the HTTP response without a per-exception handler function.
    """

    status_code: int = 500
    error_code: str = "INTERNAL_ERROR"
    docs_path: str = "internal-error"

    def __init__(self, message: str) -> None:
        self.message = message
        super().__init__(message)

    @property
    def docs_url(self) -> str:
        return f"{DOCS_TROUBLESHOOTING_URL}#{self.docs_path}"


class TaskNotFoundError(ServiceError):
    status_code = 404
    error_code = "TASK_NOT_FOUND"
    docs_path = "task-not-found"

    def __init__(self, task_id: str) -> None:
        self.task_id = task_id
        super().__init__(f"Task '{task_id}' not found.")


class TaskAlreadyTerminalError(ServiceError):
    status_code = 409
    error_code = "TASK_ALREADY_TERMINAL"
    docs_path = "task-already-terminal"

    def __init__(self, task_id: str, status: TaskStatus) -> None:
        self.task_id = task_id
        self.status = status
        super().__init__(f"Task '{task_id}' is already in terminal status '{status.value}'.")


class TaskAlreadyExistsError(ServiceError):
    status_code = 409
    error_code = "TASK_ALREADY_EXISTS"
    docs_path = "task-already-exists"

    def __init__(self, task_id: str, idempotency_key: str) -> None:
        self.task_id = task_id
        self.idempotency_key = idempotency_key
        super().__init__(
            f"Task with idempotency key '{idempotency_key}' already exists (id={task_id})."
        )


# ─── User service errors ──────────────────────────────────────────────


class UserNotFoundError(ServiceError):
    status_code = 404
    error_code = "USER_NOT_FOUND"
    docs_path = "user-not-found"

    def __init__(self, user_id: str) -> None:
        self.user_id = user_id
        super().__init__(f"User '{user_id}' not found.")


class UserAlreadyExistsError(ServiceError):
    status_code = 409
    error_code = "USER_ALREADY_EXISTS"
    docs_path = "user-already-exists"

    def __init__(self, conflict: str) -> None:
        self.conflict = conflict
        super().__init__(
            f"A user with this {conflict} already exists. Each email and each "
            f"(slack_team_id, slack_user_id) pair is unique across the directory."
        )


class TaskAlreadyClaimedError(ServiceError):
    """Another user claimed the task first (broadcast-to-channel flow)."""

    status_code = 409
    error_code = "TASK_ALREADY_CLAIMED"
    docs_path = "task-already-claimed"

    def __init__(self, task_id: str, claimed_by_user_id: str | None) -> None:
        self.task_id = task_id
        self.claimed_by_user_id = claimed_by_user_id
        super().__init__(
            f"Task '{task_id}' was already claimed by another user."
        )


class UserNoAddressError(ServiceError):
    """At least one delivery address (email or slack pair) must be set —
    a user with neither is unreachable and useless for routing."""

    status_code = 422
    error_code = "USER_NO_ADDRESS"
    docs_path = "user-no-address"

    def __init__(self) -> None:
        super().__init__(
            "A user must have at least one delivery address: either an email "
            "or a (slack_team_id, slack_user_id) pair. Rows with neither "
            "can't be reached by any channel."
        )


# ─── Setup / bootstrap errors ─────────────────────────────────────────


class SetupAlreadyCompletedError(ServiceError):
    """Tried to run /setup after a user already exists. One-shot."""

    status_code = 409
    error_code = "SETUP_ALREADY_COMPLETED"
    docs_path = "setup-already-completed"

    def __init__(self) -> None:
        super().__init__(
            "First-run setup has already been completed. Sign in with your "
            "operator credentials via /api/auth/login instead."
        )


class InvalidSetupTokenError(ServiceError):
    """Bootstrap token didn't match the in-memory value."""

    status_code = 403
    error_code = "INVALID_SETUP_TOKEN"
    docs_path = "invalid-setup-token"

    def __init__(self) -> None:
        super().__init__(
            "Invalid setup token. The token is printed to the server log on "
            "startup; restart the server to generate a fresh one."
        )
