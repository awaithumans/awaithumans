"""Server port discovery.

Enables zero-config port coordination between the server, SDK, and dashboard.

Flow:
    1. Server writes its actual bound URL to ~/.awaithumans-dev.json on startup.
    2. SDK reads that file on every call, so it finds the server regardless
       of which port the server auto-selected.
    3. Dashboard reads it via a small API route at build/runtime.
    4. Server deletes the file on graceful shutdown.

Location:
    ~/.awaithumans-dev.json (user home, stable across cwd changes)

Format:
    {
        "url": "http://localhost:3004",
        "host": "0.0.0.0",
        "port": 3004,
        "pid": 13345,
        "started_at": "2026-04-15T10:25:55Z"
    }

Environment variable AWAITHUMANS_URL always takes precedence over discovery.
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path

from awaithumans.utils.constants import DISCOVERY_FILE_NAME

logger = logging.getLogger("awaithumans.discovery")


def get_discovery_file_path() -> Path:
    """Return the path to the discovery file (~/.awaithumans-dev.json)."""
    return Path.home() / DISCOVERY_FILE_NAME


def write_discovery(*, host: str, port: int) -> None:
    """Write the server's bound URL to the discovery file.

    Called by the server on startup. The URL uses `localhost` for client
    access even when bound to `0.0.0.0`, since SDKs connect locally.
    """
    client_host = "localhost" if host in ("0.0.0.0", "::") else host
    data = {
        "url": f"http://{client_host}:{port}",
        "host": host,
        "port": port,
        "pid": os.getpid(),
        "started_at": datetime.now(timezone.utc).isoformat(),
    }
    path = get_discovery_file_path()
    try:
        path.write_text(json.dumps(data, indent=2))
        logger.info("Wrote discovery file at %s (url=%s)", path, data["url"])
    except OSError as e:
        logger.warning("Failed to write discovery file at %s: %s", path, e)


def read_discovery() -> dict | None:
    """Read the discovery file. Returns None if it doesn't exist or is invalid."""
    path = get_discovery_file_path()
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text())
        # Basic validation
        if not isinstance(data, dict) or "url" not in data:
            return None
        return data
    except (OSError, json.JSONDecodeError):
        return None


def delete_discovery() -> None:
    """Delete the discovery file. Called on graceful shutdown."""
    path = get_discovery_file_path()
    try:
        path.unlink(missing_ok=True)
        logger.info("Deleted discovery file at %s", path)
    except OSError:
        pass


def resolve_server_url(*, explicit_url: str | None = None) -> str:
    """Resolve the awaithumans server URL with this precedence:

    1. Explicit `server_url` argument passed to the SDK call.
    2. `AWAITHUMANS_URL` environment variable.
    3. Discovery file at ~/.awaithumans-dev.json.
    4. Default: http://localhost:3001.
    """
    if explicit_url:
        return explicit_url.rstrip("/")

    env_url = os.environ.get("AWAITHUMANS_URL")
    if env_url:
        return env_url.rstrip("/")

    discovered = read_discovery()
    if discovered:
        return discovered["url"].rstrip("/")

    return "http://localhost:3001"
