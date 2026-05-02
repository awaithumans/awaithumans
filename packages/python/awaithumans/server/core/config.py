"""Server configuration — all settings from environment variables.

Usage:
    from awaithumans.server.core.config import settings

All config is read from env vars with sensible defaults for development.
"""

from __future__ import annotations

from pathlib import Path

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings, loaded from environment variables."""

    # ── Server ───────────────────────────────────────────────────────
    HOST: str = "0.0.0.0"
    PORT: int = 3001
    ENVIRONMENT: str = "development"
    LOG_LEVEL: str = "INFO"

    # ── Database ─────────────────────────────────────────────────────
    DATABASE_URL: str | None = None
    DB_PATH: str = ".awaithumans/dev.db"

    # ── Dashboard auth ────────────────────────────────────────────────
    # Auth is always on. First-run state (empty users table) is handled
    # by the /api/setup bootstrap flow; see server/core/bootstrap.py.
    # All /api/* routes except the public prefix list require a valid
    # session cookie or the admin bearer token.

    # ── CORS ──────────────────────────────────────────────────────────
    CORS_ORIGINS: str = "*"  # Comma-separated list, or "*" for all

    # ── Email channel ────────────────────────────────────────────────
    # Server-wide default identity for email notifications. Per-task
    # `notify=["email+acme-prod:alice@..."]` overrides this.
    EMAIL_TRANSPORT: str | None = None      # "resend" | "smtp" | "logging" | "noop"
    EMAIL_FROM: str | None = None           # "notifications@acme.com"
    EMAIL_FROM_NAME: str | None = None      # "Acme Tasks"
    EMAIL_REPLY_TO: str | None = None
    # Resend transport.
    RESEND_KEY: str | None = None
    # SMTP transport.
    SMTP_HOST: str | None = None
    SMTP_PORT: int = 587
    SMTP_USER: str | None = None
    SMTP_PASSWORD: str | None = None
    SMTP_USE_TLS: bool = False   # Implicit TLS (port 465). Rare.
    SMTP_START_TLS: bool = True  # STARTTLS on port 587. Most common.

    # Admin API token gates identity-management endpoints
    # (POST/DELETE /api/channels/email/identities, etc.).
    # Without this set, admin endpoints return 503.
    ADMIN_API_TOKEN: str | None = None

    # ── Notifications ────────────────────────────────────────────────
    SLACK_WEBHOOK: str | None = None
    # Static bot token for SINGLE-WORKSPACE self-hosted setups. Leave
    # unset and use CLIENT_ID/CLIENT_SECRET below for multi-workspace.
    SLACK_BOT_TOKEN: str | None = None
    SLACK_SIGNING_SECRET: str | None = None
    # OAuth credentials for MULTI-WORKSPACE distribution. When all three
    # (CLIENT_ID, CLIENT_SECRET, INSTALL_TOKEN) are set, the OAuth install
    # flow is enabled at /api/channels/slack/oauth/start.
    SLACK_CLIENT_ID: str | None = None
    SLACK_CLIENT_SECRET: str | None = None
    # Operator-only shared secret required to initiate an install.
    # Without this, any visitor who knows PUBLIC_URL could install their
    # own workspace into the server and receive notifications. Generate
    # a high-entropy value (e.g. `openssl rand -hex 32`) and share it
    # only with authorized admins. REQUIRED when OAuth is enabled.
    SLACK_INSTALL_TOKEN: str | None = None
    # Scopes requested during OAuth install. Override only if you need a
    # tighter or broader scope set than the default manifest.
    SLACK_OAUTH_SCOPES: str | None = None

    # ── Public URLs ──────────────────────────────────────────────────
    # Used when building link-out URLs in Slack/email so humans can
    # click through to the dashboard. In production, this is the
    # HTTPS URL of the server (which also serves the dashboard).
    PUBLIC_URL: str = "http://localhost:3001"

    # ── Verification ─────────────────────────────────────────────────
    ANTHROPIC_API_KEY: str | None = None

    def get_secret(self, env_name: str) -> str | None:
        """Read a secret value through Settings rather than raw os.environ.

        Verifier providers (and any other code paths that need to
        consume an operator-managed secret keyed by env-var name)
        should funnel through here. Two reasons:

          1. CLAUDE.md §6 forbids raw `os.environ.get(...)` outside
             `core/config.py`. Concentrating reads here gives us one
             place to add scrubbing / audit / `.env` normalisation in
             the future without chasing call sites.
          2. The pydantic-settings model picks up declared fields
             automatically (e.g. `ANTHROPIC_API_KEY`) — a bare
             `os.environ.get()` would miss `.env` loading on those.
             We try the model attribute first, then fall back to
             `os.environ` for fields the operator added themselves
             via VerifierConfig.api_key_env without us pre-declaring
             a Settings field for them.

        Returns None when the variable is unset, so callers can raise
        their own typed errors (e.g. VerifierAPIKeyMissingError).
        """
        import os as _os

        # Match attribute name case-insensitively against declared
        # Settings fields (CLAUDE.md leans on the pydantic-settings
        # `case_sensitive=False` config we already set).
        attr = getattr(self, env_name.upper(), None)
        if isinstance(attr, str) and attr:
            return attr
        return _os.environ.get(env_name) or None

    # ── Payload ──────────────────────────────────────────────────────
    PAYLOAD_KEY: str | None = None  # AES-256-GCM encryption key
    MAX_PAYLOAD_SIZE_MB: int = 5

    # NOTE: We deliberately do NOT carry a `WEBHOOK_SECRET` setting any
    # more. An earlier version had `WEBHOOK_SECRET: str =
    # "awaithumans-dev-secret"` — unused but a footgun: as soon as any
    # outbound-webhook signing code referenced it, every deployment
    # that didn't override the env var would HMAC with a value
    # publicly visible in the GitHub repo. If outbound webhook signing
    # is reintroduced, declare the field as `str | None = None` and
    # fail-fast in `app.py` when the dependent code path runs without
    # an explicit operator-set value, mirroring the PAYLOAD_KEY guard.

    model_config = {
        "env_prefix": "AWAITHUMANS_",
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "case_sensitive": False,
    }

    @property
    def database_url_async(self) -> str:
        """Resolved async database URL."""
        if self.DATABASE_URL:
            url = self.DATABASE_URL
            if url.startswith("postgres://"):
                return url.replace("postgres://", "postgresql+asyncpg://", 1)
            if url.startswith("postgresql://"):
                return url.replace("postgresql://", "postgresql+asyncpg://", 1)
            return url

        Path(self.DB_PATH).parent.mkdir(parents=True, exist_ok=True)
        return f"sqlite+aiosqlite:///{self.DB_PATH}"

    @property
    def database_url_sync(self) -> str:
        """Resolved sync database URL (for migrations)."""
        if self.DATABASE_URL:
            url = self.DATABASE_URL
            if url.startswith("postgres://"):
                return url.replace("postgres://", "postgresql://", 1)
            return url

        Path(self.DB_PATH).parent.mkdir(parents=True, exist_ok=True)
        return f"sqlite:///{self.DB_PATH}"

    @property
    def cors_origin_list(self) -> list[str]:
        """Parse CORS_ORIGINS into a list."""
        if self.CORS_ORIGINS == "*":
            return ["*"]
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]

    @property
    def is_production(self) -> bool:
        return self.ENVIRONMENT.upper() == "PRODUCTION"


settings = Settings()
