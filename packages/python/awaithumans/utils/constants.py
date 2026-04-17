"""Project-wide constants.

All magic numbers, configuration defaults, and shared values live here.
Import from here, not from individual modules.
"""

from __future__ import annotations

from awaithumans.types import TaskStatus

# ─── Project Identity ────────────────────────────────────────────────────

SERVICE_NAME = "awaithumans"
DOCS_BASE_URL = "https://awaithumans.dev/docs"
DOCS_TROUBLESHOOTING_URL = f"{DOCS_BASE_URL}/troubleshooting"
DOCS_ROADMAP_URL = f"{DOCS_BASE_URL}/roadmap"

# ─── Timeout ─────────────────────────────────────────────────────────────

MIN_TIMEOUT_SECONDS = 60          # 1 minute — minimum allowed timeout
MAX_TIMEOUT_SECONDS = 2_592_000   # 30 days — maximum allowed timeout

# ─── Long-Poll ───────────────────────────────────────────────────────────

POLL_INTERVAL_SECONDS = 25        # reconnection interval, must stay under gateway timeouts (60s)

# ─── Timeout Scheduler ───────────────────────────────────────────────────

TIMEOUT_CHECK_INTERVAL_SECONDS = 5  # how often the scheduler checks for expired tasks

# ─── Task Status Sets ────────────────────────────────────────────────────

TERMINAL_STATUSES_SET = frozenset({
    TaskStatus.COMPLETED,
    TaskStatus.TIMED_OUT,
    TaskStatus.CANCELLED,
    TaskStatus.VERIFICATION_EXHAUSTED,
})

# ─── Payload ─────────────────────────────────────────────────────────────

MAX_PAYLOAD_SIZE_BYTES = 5 * 1024 * 1024   # 5 MB hard limit

# ─── Port Discovery ──────────────────────────────────────────────────────

# Where the server writes its port + URL so SDKs and the dashboard can auto-discover it.
# Located in the user's home directory so it's stable across cwd changes.
DISCOVERY_FILE_NAME = ".awaithumans-dev.json"

# ─── Slack Channel ───────────────────────────────────────────────────────

# Slack rejects requests whose timestamp is more than this many seconds old
# (prevents replay attacks).
SLACK_SIGNATURE_MAX_AGE_SECONDS = 300  # 5 minutes

# Block Kit action_id for the "Review" button in the initial notification.
SLACK_ACTION_OPEN_REVIEW = "awaithumans.open_review"

# Block Kit callback_id for the review modal (matches on view_submission).
SLACK_MODAL_CALLBACK_ID = "awaithumans.review_modal"

# Prefix on Block Kit block_ids so we can recognize our own blocks and
# extract the field name deterministically.
SLACK_BLOCK_ID_PREFIX = "awaithumans:"

# notify= string prefix for Slack destinations. Examples:
#   "slack:#approvals"  → channel
#   "slack:@U123ABC"    → user (Slack user ID, starts with U or W)
SLACK_NOTIFY_PREFIX = "slack:"

# OAuth state is a signed, time-bounded nonce. Expires if the user takes
# more than this long to complete the install consent.
SLACK_OAUTH_STATE_MAX_AGE_SECONDS = 600  # 10 minutes

# Bot scopes we request during OAuth install. Kept in sync with
# channels/slack/app_manifest.yaml. Used as the default value for
# SLACK_OAUTH_SCOPES when the env var isn't overridden.
SLACK_DEFAULT_OAUTH_SCOPES = (
    "chat:write,im:write,channels:read,groups:read,"
    "users:read,files:write,files:read"
)

# Name of the cookie holding the OAuth state nonce — read from both
# /oauth/start (set) and /oauth/callback (verify + delete).
SLACK_OAUTH_STATE_COOKIE_NAME = "awaithumans_slack_oauth_state"

# Block Kit hard limits — text length caps and select-option counts.
# These are enforced by the Slack API itself; we truncate to stay well
# inside and fail loudly rather than have Slack silently drop blocks.
SLACK_HEADER_TEXT_MAX = 150
SLACK_PLAIN_TEXT_MAX = 3000
SLACK_SELECT_MAX_OPTIONS = 100
SLACK_CONTEXT_VALUE_MAX = 200   # payload-context key:value truncation in the modal header

# ─── Email Channel ───────────────────────────────────────────────────────

# Default TTL for magic-link action tokens. 24 hours covers "user comes
# back tomorrow morning"; 1 hour was too tight in practice.
MAGIC_LINK_MAX_AGE_SECONDS = 24 * 60 * 60

# HKDF parameters for deriving the magic-link HMAC key from PAYLOAD_KEY.
# The salt is channel-scoped so the same root key could derive keys for
# other channels without primitives colliding. `info` is a version tag —
# bump it on any breaking change to the token format.
MAGIC_LINK_HKDF_SALT = b"awaithumans-email-magic-links"
MAGIC_LINK_HKDF_INFO = b"v1"

# HMAC-SHA256 digest length. Used to slice mac || body when verifying
# magic-link tokens. Named so the slice isn't a magic number.
HMAC_SHA256_DIGEST_BYTES = 32

# Identity IDs are used in URLs (DELETE /identities/{id}) and in the
# `notify=` routing prefix (`email+acme:user@…`). 100 is more than enough
# for any human-chosen slug and short enough to keep URLs sane.
EMAIL_IDENTITY_ID_MAX_LENGTH = 100
