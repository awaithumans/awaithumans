# langgraph-ts — TypeScript LangGraph + awaithumans

A refund-approval graph with one human-in-the-loop interrupt. Mirrors
the `temporal-ts/` example in shape but uses LangGraph's interrupt /
resume model instead of Temporal signals.

## What you'll see

```
[customer]
   │
   ▼
[POST /start]           ─── 250  ──► [graph.invoke]
                                       └─► checkPolicy → humanReview
                                                          │
                                                          │  awaitHuman()
                                                          │  POSTs to awaithumans
                                                          │  → interrupt() throws
                                                          │
                                       ◄── { __interrupt__ } ──┘
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
[graph.invoke(Command({resume}))]
   │
   ▼
[humanReview node returns]
   │
   ▼
[final state visible via /threads/:id]
```

## Prerequisites

- Node 20+
- [uv](https://docs.astral.sh/uv/) if you're booting the server via `npx awaithumans dev`. Install with `curl -LsSf https://astral.sh/uv/install.sh | sh`.
- `awaithumans dev` running locally (in another terminal). The TS SDK auto-discovers the URL + admin token via `~/.awaithumans-dev.json`.
- The LangGraph adapter peer dep. This example's `package.json` already lists `@langchain/langgraph`. If you're copying this code into your own project, run `npm install awaithumans @langchain/langgraph`.
- Both this app and the awaithumans server need the **same** `AWAITHUMANS_PAYLOAD_KEY`. The dev server writes its key to `<cwd-of-awaithumans-dev>/.awaithumans/payload.key` on first boot — find that path and export it as shown in step 2 below.

## Run it

In three terminals:

```bash
# Terminal 1 — awaithumans server
awaithumans dev

# Terminal 2 — this example's app (graph + checkpointer + callback)
cd examples/langgraph-ts
npm install

# AWAITHUMANS_PAYLOAD_KEY lives at .awaithumans/payload.key relative to wherever
# you ran `awaithumans dev`. Easiest way to find it:
#   cd <that-directory> && pwd && ls .awaithumans/payload.key
# Then point this export at it:
export AWAITHUMANS_PAYLOAD_KEY=$(cat /path/to/awaithumans-dev-cwd/.awaithumans/payload.key)
# Demo-only: pre-assign every human-review task to your dashboard
# login so the Approve / Reject form renders immediately. Leave
# unset in production — operators claim tasks from the dashboard.
export AWAITHUMANS_DEMO_ASSIGN_TO="you@example.com"
npm run app

# Terminal 3 — kick off a run
cd examples/langgraph-ts
npm run kickoff -- 250 cus_demo    # over threshold → human review
# or
npm run kickoff -- 50 cus_small    # under threshold → auto-approves
```

Then approve in the awaithumans dashboard (http://localhost:3001) or
via `curl -X POST .../api/tasks/{id}/complete`.

## How the pieces fit

- **`graph.ts`** — defines `RefundState`, three nodes (`checkPolicy`,
  `humanReview`, `autoApprove`), a `MemorySaver` checkpointer, and a
  conditional edge. The `humanReview` node calls `awaitHuman` from
  `awaithumans/langgraph` — that's the entire HITL integration.

- **`app.ts`** — single Hono process. Owns the compiled graph (so
  `/start` and `/awaithumans/cb` share state via the checkpointer),
  exposes `POST /start` to kick off, `POST /awaithumans/cb` to receive
  the webhook, and `GET /threads/:id` for the kickoff client to poll.

- **`kickoff.ts`** — POSTs `/start`, then polls `/threads/:id` until
  the graph reports a final state.

## Production notes

- **Checkpointer**: this demo uses `MemorySaver` (in-process, lost on
  restart). Production should swap in `@langchain/langgraph-checkpoint-sqlite`
  or `@langchain/langgraph-checkpoint-postgres` so an interrupted graph
  survives a redeploy.

- **Webhook reachability**: the awaithumans server has to reach
  `${callback_base}/awaithumans/cb`. For local dev with `awaithumans dev`
  on the same machine that's `http://localhost:8765`. For a remote
  awaithumans server pointing at a local app, expose this process via
  ngrok and set `AWAITHUMANS_CALLBACK_BASE=https://<ngrok>.io`.

- **Webhook delivery durability**: the awaithumans server retries
  webhook POSTs with backoff for up to 3 days (PR #61), so a brief
  app outage won't lose the resume signal.
