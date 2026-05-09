"""Partner-side server for the embed example.

Runs a tiny Flask app at http://localhost:5000 that:
  1. Calls await_human() to create a refund-approval task.
  2. Mints an embed URL for that task.
  3. Serves index.html which iframes the URL.

Prereqs (3 terminals):

    # Terminal 1 — awaithumans server + dashboard
    awaithumans dev

    # Terminal 2 — once, then save the ah_sk_* it prints
    awaithumans create-service-key --name dev

    # Then add to your awaithumans server's environment:
    #   AWAITHUMANS_EMBED_SIGNING_SECRET=<openssl rand -hex 32>
    #   AWAITHUMANS_EMBED_PARENT_ORIGINS=http://localhost:5000
    # and restart Terminal 1.

    # Terminal 3 — partner backend
    pip install flask awaithumans
    AH_SERVICE_KEY=ah_sk_... python examples/embed/server.py

Then open http://localhost:5000 and click "Start approval".
"""

from __future__ import annotations

import os

from flask import Flask, jsonify, send_from_directory
from pydantic import BaseModel

from awaithumans import await_human_sync, embed_token_sync


HERE = os.path.dirname(os.path.abspath(__file__))


class RefundReq(BaseModel):
    amount: float
    customer: str


class Decision(BaseModel):
    approved: bool


app = Flask(__name__)


@app.route("/")
def home() -> object:
    return send_from_directory(HERE, "index.html")


@app.route("/api/start-approval")
def start_approval() -> object:
    """Create a task and mint an embed URL for the demo user."""
    task = await_human_sync(
        task="Approve refund?",
        payload_schema=RefundReq,
        payload=RefundReq(amount=240, customer="cus_123"),
        response_schema=Decision,
        timeout_seconds=900,
    )
    embed = embed_token_sync(
        task_id=task.id,
        sub="acme:demo_user",
        parent_origin="http://localhost:5000",
        api_key=os.environ["AH_SERVICE_KEY"],
    )
    return jsonify({"approval_url": embed.embed_url})


if __name__ == "__main__":
    app.run(port=5000, debug=True)
