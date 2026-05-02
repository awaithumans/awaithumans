"""FastAPI callback receiver — converts awaithumans webhooks to Temporal signals.

This process lives between the awaithumans server (which fires the
webhook) and the Temporal workflow (which is parked waiting for a
signal). It does three things:

  1. Receive POST /awaithumans/callback with the workflow ID in the
     query string and the signed body in the request.
  2. Verify the HMAC signature (proves the webhook came from your
     awaithumans server, not an attacker).
  3. Look up the running workflow by ID and signal it.

Run with:
    uvicorn callback_server:app --host 0.0.0.0 --port 8765

For the awaithumans server (running locally) to reach this from
inside Docker / from a hosted deployment, expose it via a tunnel:
    ngrok http 8765
    export AWAITHUMANS_CALLBACK_BASE=https://<ngrok-id>.ngrok.io

The same `AWAITHUMANS_PAYLOAD_KEY` env var must be set on BOTH this
process and the awaithumans server — that's how HMAC keys derive
to the same value on both sides.
"""

from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI, HTTPException, Request
from temporalio.client import Client

from awaithumans.adapters.temporal import dispatch_signal

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("examples.temporal.callback_server")

TEMPORAL_ADDRESS = os.environ.get("TEMPORAL_ADDRESS", "localhost:7233")

# The Temporal client is a long-lived connection — opening one per
# request would burn 50ms+ on handshake. We hold a module-level
# singleton populated during the lifespan startup.
_client: Client | None = None


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    global _client
    _client = await Client.connect(TEMPORAL_ADDRESS)
    logger.info("Connected to Temporal at %s", TEMPORAL_ADDRESS)
    yield
    # No explicit close — Client doesn't expose one and process exit
    # collects sockets.


app = FastAPI(lifespan=lifespan)


@app.post("/awaithumans/callback")
async def callback(request: Request, wf: str) -> dict:
    """Receive an awaithumans webhook and signal the Temporal workflow.

    `wf` is the workflow ID — the awaithumans adapter encodes it into
    `callback_url` when creating the task. We don't trust headers
    or bodies for routing; the workflow ID comes from a URL the
    workflow itself constructed."""
    if _client is None:
        raise HTTPException(status_code=503, detail="Temporal client not ready.")

    body = await request.body()
    signature = request.headers.get("x-awaithumans-signature")

    try:
        await dispatch_signal(
            temporal_client=_client,
            workflow_id=wf,
            body=body,
            signature_header=signature,
        )
    except PermissionError as exc:
        # Bad signature — security event, log + return 401.
        logger.warning("Rejected webhook with bad signature: %s", exc)
        raise HTTPException(status_code=401, detail=str(exc)) from exc
    except ValueError as exc:
        # Malformed body — return 400 so the awaithumans server's
        # logs flag the misconfig.
        logger.warning("Rejected malformed webhook: %s", exc)
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return {"ok": True}
