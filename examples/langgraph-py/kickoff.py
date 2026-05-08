"""Kickoff — start one refund run by hitting the app's /start endpoint.

In a real system this would be a request from the user's product
surface (e.g. "customer hits 'request refund'"). For the demo it's
a CLI script that:

  1. POSTs /start to kick off a graph run
  2. If auto-approved: prints the final state and exits
  3. If interrupted: polls /threads/{id} until it sees a final state
     (the human submits via the dashboard, the awaithumans webhook
     fires, the app resumes the graph, and the next poll sees the
     result)

Usage:
    python kickoff.py 250 cus_demo
    python kickoff.py 50 cus_small      # auto-approves under threshold
"""

from __future__ import annotations

import asyncio
import json
import os
import sys

import httpx

APP_URL = os.environ.get("APP_URL", "http://localhost:8765")
POLL_INTERVAL_SECONDS = 2.0
POLL_MAX_TRIES = 240  # 8 minutes — plenty for a demo


async def main() -> None:
    amount_usd = float(sys.argv[1] if len(sys.argv) > 1 else "250")
    customer_id = sys.argv[2] if len(sys.argv) > 2 else "cus_demo"

    async with httpx.AsyncClient(timeout=10) as client:
        start_resp = await client.post(
            f"{APP_URL}/start",
            json={"customer_id": customer_id, "amount_usd": amount_usd},
        )
        if start_resp.status_code >= 400:
            print(f"[kickoff] /start returned {start_resp.status_code}: "
                  f"{start_resp.text}")
            sys.exit(1)
        start = start_resp.json()

        if start["status"] == "completed":
            print("[kickoff] result:", json.dumps(start["state"], indent=2))
            return

        thread_id = start["thread_id"]
        print(f"[kickoff] thread={thread_id} paused — awaiting human")
        print("[kickoff] interrupt payload:")
        print(json.dumps(start["interrupts"], indent=2))

        for _ in range(POLL_MAX_TRIES):
            await asyncio.sleep(POLL_INTERVAL_SECONDS)
            r = await client.get(f"{APP_URL}/threads/{thread_id}")
            if r.status_code >= 400:
                print(f"[kickoff] poll {r.status_code}")
                continue
            s = r.json()
            # "Done" = no pending interrupt and `approved` is set.
            if not s.get("interrupts") and s.get("values", {}).get("approved") is not None:
                print("[kickoff] result:", json.dumps(s["values"], indent=2))
                return

    print("[kickoff] timed out waiting for human")
    sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
