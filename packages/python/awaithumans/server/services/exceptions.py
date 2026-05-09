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
        super().__init__(f"Task '{task_id}' was already claimed by another user.")


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


class LastOperatorError(ServiceError):
    """Tried to delete / demote / deactivate the only active operator.

    Prevents locking everyone out of dashboard admin — the last
    operator standing has to stay reachable. Recovery from a full
    lockout requires CLI (bootstrap-operator on empty DB) or the
    admin bearer token, both of which are operator-level already."""

    status_code = 409
    error_code = "LAST_OPERATOR"
    docs_path = "last-operator"

    def __init__(self, action: str) -> None:
        self.action = action
        super().__init__(
            f"Can't {action} the last active operator — at least one "
            "operator must remain so the dashboard stays manageable. "
            "Promote another user to operator first."
        )


# ─── Verifier errors ──────────────────────────────────────────────────


class VerifierProviderUnavailableError(ServiceError):
    """The configured verifier provider's SDK isn't installed.

    Surfaces the exact `pip install` line so the operator can fix it
    without hunting through docs."""

    status_code = 500
    error_code = "VERIFIER_PROVIDER_UNAVAILABLE"
    docs_path = "verifier-provider-unavailable"

    def __init__(self, provider: str, extra: str) -> None:
        self.provider = provider
        self.extra = extra
        super().__init__(
            f"Verifier provider '{provider}' requires the [{extra}] extra. "
            f'Install with: pip install "awaithumans[{extra}]"'
        )


class VerifierAPIKeyMissingError(ServiceError):
    """The env var named in VerifierConfig.api_key_env wasn't set on the server."""

    status_code = 500
    error_code = "VERIFIER_API_KEY_MISSING"
    docs_path = "verifier-api-key-missing"

    def __init__(self, env_var: str) -> None:
        self.env_var = env_var
        super().__init__(
            f"Verifier API key not configured. Set the '{env_var}' environment "
            "variable on the awaithumans server (not in the agent process)."
        )


class VerifierEndpointMissingError(ServiceError):
    """A vendor endpoint env var wasn't set (Azure OpenAI requires both
    a key and an endpoint URL).

    Distinct from VERIFIER_API_KEY_MISSING so the operator-facing error
    points at the right thing — saying 'API key missing' when the key
    is set but the endpoint URL isn't is a 30-minute debugging detour."""

    status_code = 500
    error_code = "VERIFIER_ENDPOINT_MISSING"
    docs_path = "verifier-endpoint-missing"

    def __init__(self, env_var: str) -> None:
        self.env_var = env_var
        super().__init__(
            f"Verifier endpoint URL not configured. Set the '{env_var}' "
            "environment variable on the awaithumans server."
        )


class VerifierConfigInvalidError(ServiceError):
    """A task's stored `verifier_config` JSON doesn't match the current
    VerifierConfig schema.

    Common cause: a task was created against an older SDK that wrote a
    field shape we've since changed. The task can't be verified, but
    it's not the human's fault — surface a clear error to the operator
    so they know whether to bump the SDK or override the verifier."""

    status_code = 422
    error_code = "VERIFIER_CONFIG_INVALID"
    docs_path = "verifier-config-invalid"

    def __init__(self, detail: str) -> None:
        self.detail = detail
        super().__init__(
            f"The task's stored verifier_config doesn't match the current schema: {detail}"
        )


class VerifierProviderError(ServiceError):
    """Provider rejected the verification call (network, auth, quota, model errors).

    Distinct from VERIFIER_API_KEY_MISSING (config) and from a 'failed'
    VerifierResult (the LLM ran successfully but said the response is
    bad). This means the LLM call itself blew up."""

    status_code = 502
    error_code = "VERIFIER_PROVIDER_ERROR"
    docs_path = "verifier-provider-error"

    def __init__(self, provider: str, detail: str) -> None:
        self.provider = provider
        self.detail = detail
        super().__init__(f"Verifier provider '{provider}' failed: {detail}")


class VerifierProviderUnknownError(ServiceError):
    """VerifierConfig.provider is set to something we don't recognise."""

    status_code = 422
    error_code = "VERIFIER_PROVIDER_UNKNOWN"
    docs_path = "verifier-provider-unknown"

    def __init__(self, provider: str, known: list[str]) -> None:
        self.provider = provider
        self.known = known
        super().__init__(
            f"Unknown verifier provider '{provider}'. Supported providers: {', '.join(known)}."
        )


# ── Dashboard embedding ──────────────────────────────────────────────
# See docs/superpowers/specs/2026-05-06-dashboard-embedding-design.md
# §3 (mint endpoint), §5.1 (EmbedAuthMiddleware), §7 (security model).


class InvalidEmbedTokenError(ServiceError):
    """Embed JWT failed signature, audience, expiry, or claim checks."""

    status_code = 401
    error_code = "INVALID_EMBED_TOKEN"
    docs_path = "invalid-embed-token"

    def __init__(self, *, reason: str) -> None:
        self.reason = reason
        super().__init__(f"Invalid embed token: {reason}.")


class EmbedOriginNotAllowedError(ServiceError):
    """parent_origin in the mint request is not in the tenant allowlist."""

    status_code = 400
    error_code = "EMBED_ORIGIN_NOT_ALLOWED"
    docs_path = "embed-origin-not-allowed"

    def __init__(self, *, origin: str) -> None:
        self.origin = origin
        super().__init__(f"Origin '{origin}' is not in the embed allowlist.")


class ServiceKeyNotFoundError(ServiceError):
    """The Authorization bearer didn't resolve to a known service key."""

    status_code = 401
    error_code = "SERVICE_KEY_NOT_FOUND"
    docs_path = "service-key-not-found"

    def __init__(self) -> None:
        super().__init__("Service key not recognised or revoked.")
