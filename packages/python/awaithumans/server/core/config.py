"""Server configuration — all settings from environment variables.

Usage:
    from awaithumans.server.core.config import settings

All config is read from env vars with sensible defaults for development.
"""

from __future__ import annotations

import os
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

    # ── Auth ──────────────────────────────────────────────────────────
    DASHBOARD_USER: str = "admin"
    DASHBOARD_PASSWORD: str = "admin"

    # ── CORS ──────────────────────────────────────────────────────────
    CORS_ORIGINS: str = "*"  # Comma-separated list, or "*" for all

    # ── Notifications ────────────────────────────────────────────────
    SLACK_WEBHOOK: str | None = None
    SLACK_BOT_TOKEN: str | None = None
    RESEND_KEY: str | None = None

    # ── Verification ─────────────────────────────────────────────────
    ANTHROPIC_API_KEY: str | None = None

    # ── Payload ──────────────────────────────────────────────────────
    PAYLOAD_KEY: str | None = None  # AES-256-GCM encryption key
    MAX_PAYLOAD_SIZE_MB: int = 5

    # ── Webhook ──────────────────────────────────────────────────────
    WEBHOOK_SECRET: str = "awaithumans-dev-secret"  # HMAC signing secret

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
