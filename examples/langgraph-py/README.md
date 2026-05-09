# langgraph-py — Python LangGraph + awaithumans

A refund-approval graph with one human-in-the-loop interrupt. Mirrors
`examples/langgraph-ts/` in Python: same shape, same routes, same
end-to-end flow.

## What you'll see

```
[customer]
   │
   ▼
[POST /start]           ─── 250  ──► [graph.ainvoke]
                                       └─► check_policy → human_review
                                                          │
                                                          │  await_human()
                                                          │  POSTs to awaithumans
                                                          │  → interrupt() throws
                                                          │
                                       ◄── interrupted ──┘
                                       (graph paused;
                                        state in checkpointer)

[human approves in dashboard]
   │
   ▼
[awaithumans server fires webhook]
   │
   ▼
[POST /awaithumans/cb?thread=…]
   │
   ▼
[handler verifies HMAC]
   │
   ▼
[graph.ainvoke(Command(resume=…))]
   │
   ▼
[human_review node returns]
   │
   ▼
[final state visible via /threads/:id]
```

## Prerequisites

- Python 3.10+
- `awaithumans dev` running locally (in another terminal). The Python SDK auto-discovers the URL + admin token via `~/.awaithumans-dev.json`.
- The LangGraph adapter extra. This example's `requirements.txt` installs `awaithumans[langgraph]` for you. If you're copying this code into your own project, run `pip install "awaithumans[langgraph]"` — without the extra, importing `awaithumans.adapters.langgraph` fails.
- Both this app and the awaithumans server need the **same** `AWAITHUMANS_PAYLOAD_KEY`. The dev server writes its key to `<cwd-of-awaithumans-dev>/.awaithumans/payload.key` on first boot — find that path and export it as shown in step 2 below.

## Run it

In three terminals:

```bash
# Terminal 1 — awaithumans server
awaithumans dev

# Terminal 2 — this example's app (graph + checkpointer + callback)
cd examples/langgraph-py
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# AWAITHUMANS_PAYLOAD_KEY lives at .awaithumans/payload.key relative to wherever
# you ran `awaithumans dev`. Easiest way to find it:
#   cd <that-directory> && pwd && ls .awaithumans/payload.key
# Then point this export at it:
export AWAITHUMANS_PAYLOAD_KEY=$(cat /path/to/awaithumans-dev-cwd/.awaithumans/payload.key)
# Demo-only: pre-assign every human-review task to your dashboard
# login so the Approve / Reject form renders immediately. Leave
# unset in production — operators claim tasks from the dashboard.
export AWAITHUMANS_DEMO_ASSIGN_TO="you@example.com"
uvicorn app:app --host 0.0.0.0 --port 8765

# Terminal 3 — kick off a run
cd examples/langgraph-py
source .venv/bin/activate
python kickoff.py 250 cus_demo    # over threshold → human review
# or
python kickoff.py 50 cus_small    # under threshold → auto-approves
```

Then approve in the awaithumans dashboard (http://localhost:3001) or
via `curl -X POST .../api/tasks/{id}/complete`.

## How the pieces fit

- **`graph.py`** — defines `RefundState`, three nodes, a `MemorySaver`
  checkpointer, and a conditional edge. `human_review` calls
  `await_human` from `awaithumans.adapters.langgraph` — that's the
  whole HITL integration.

- **`app.py`** — single FastAPI process. Owns the compiled graph (so
  `/start` and `/awaithumans/cb` share state via the checkpointer),
  exposes `POST /start` to kick off, `POST /awaithumans/cb` to receive
  the webhook, and `GET /threads/:id` for the kickoff client to poll.

- **`kickoff.py`** — POSTs `/start`, then polls `/threads/:id` until
  the graph reports a final state.

## Production notes

- **Checkpointer**: this demo uses `MemorySaver` (in-process, lost on
  restart). Production should swap in `langgraph.checkpoint.sqlite`
  or `langgraph.checkpoint.postgres` so an interrupted graph survives
  a redeploy.

- **Webhook reachability**: the awaithumans server has to reach
  `${callback_base}/awaithumans/cb`. For local dev with `awaithumans dev`
  on the same machine that's `http://localhost:8765`. For a remote
  awaithumans server pointing at a local app, expose this process via
  ngrok and set `AWAITHUMANS_CALLBACK_BASE=https://<ngrok>.io`.

- **Webhook delivery durability**: the awaithumans server retries
  webhook POSTs with backoff for up to 3 days, so a brief app outage
  won't lose the resume signal.
