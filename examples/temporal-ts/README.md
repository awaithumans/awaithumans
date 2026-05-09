# Temporal × awaithumans — TypeScript example

A real Temporal workflow that pauses for a human approval through awaithumans, then continues. TypeScript counterpart of [`../temporal/`](../temporal/) (Python).

This is the canonical durable-HITL pattern: the workflow's `awaitHuman()` call gives Temporal back to the scheduler ("park me until a signal arrives"), the human reviews via the awaithumans dashboard / Slack / email, and a webhook from the awaithumans server signals the workflow back to life. Zero compute consumed while waiting; full Temporal durability if the worker restarts mid-await.

## Prerequisites

- Node 20+
- [uv](https://docs.astral.sh/uv/) — `npx awaithumans dev` (and `awaithumans dev` directly) uses it under the hood to run the Python server. Install with `curl -LsSf https://astral.sh/uv/install.sh | sh`.
- The Temporal CLI — `brew install temporal` on macOS; see [temporal.io/setup-cli](https://docs.temporal.io/cli) for Linux / Windows.
- `awaithumans dev` running locally (step 2 below). The SDK auto-discovers it via `~/.awaithumans-dev.json`.
- The Temporal adapter has peer deps on `@temporalio/workflow` and `@temporalio/client`. This example's `package.json` already lists them. If you're copying this code into your own project, run `npm install awaithumans @temporalio/workflow @temporalio/client`.

## Architecture

```
┌──────────────────┐  HTTP POST /api/tasks   ┌──────────────────────┐
│ Temporal worker  │ ─────────────────────►  │ awaithumans server   │
│ (refundWorkflow) │                         │ (awaithumans dev)    │
│                  │                         │                      │
│ awaitHuman()     │                         │ — human reviews ──►  │
│   parked         │                         │ — completes task ──► │
│                  │  webhook (signed)       │                      │
│                  │ ◄───────────────────────│                      │
└─────┬────────────┘                         └──────────────────────┘
      │ Temporal signal
      │ (via dispatchSignal)
┌─────▼────────────────┐
│ Hono callback server │
│ (callback-server.ts) │
└──────────────────────┘
```

Three processes:

| Process              | What it does                                    | Command                       |
|----------------------|-------------------------------------------------|-------------------------------|
| awaithumans server   | Stores tasks, hosts dashboard, fires webhooks   | `awaithumans dev`             |
| Temporal worker      | Runs the workflow                               | `npm run worker`              |
| Callback receiver    | Converts webhooks → Temporal signals            | `npm run callback-server`     |

Plus a one-shot kickoff to start a workflow run:

```sh
npm run kickoff -- 250 cus_demo
```

## Run it locally

### 1. Boot Temporal (separate terminal)

```sh
brew install temporal           # or see temporal.io/setup-cli
temporal server start-dev       # localhost:7233 + UI at :8233
```

### 2. Boot the awaithumans server (separate terminal)

```sh
awaithumans dev
```

Open the printed `/setup?token=...` URL and create your operator user.

### 3. Install this example

```sh
cd examples/temporal-ts
npm install
```

### 4. Boot the callback receiver (separate terminal)

The callback receiver verifies the webhook signature using `AWAITHUMANS_PAYLOAD_KEY`, which `awaithumans dev` generated for you. Both processes need the same value.

```sh
export AWAITHUMANS_PAYLOAD_KEY=$(cat <wherever-you-ran-awaithumans-dev>/.awaithumans/payload.key)
npm run callback-server
# → [callback] listening on http://localhost:8765
```

### 5. Boot the Temporal worker (separate terminal)

```sh
cd examples/temporal-ts
npm run worker
# → [worker] task_queue=awaithumans-refunds
# → [worker] running — Ctrl-C to stop
```

### 6. Kick off a workflow run

```sh
cd examples/temporal-ts
npm run kickoff -- 250 cus_demo
# → [kickoff] started workflow id=refund-...
# → [kickoff] waiting for human via dashboard / Slack / email
```

The kickoff script reads `AWAITHUMANS_URL` + `AWAITHUMANS_ADMIN_API_TOKEN` from env or the dev server's discovery file (`~/.awaithumans-dev.json`) — no manual export needed if `awaithumans dev` is running.

### 7. Review

Open http://localhost:3001 — you'll see "Approve $250 refund for cus_demo?" in the queue. Click through, fill the form, Submit.

The kickoff terminal prints the workflow result as a JSON object, then exits:

```
[kickoff] workflow result: {
  "refundId": "refund-1234abcd-...",
  "outcome": "approved",
  "notes": "Looks legitimate"
}
```

The Temporal UI at http://localhost:8233 shows the full workflow event history — `awaitHuman` activity, signal received, `processRefund` activity, completion.

## What this exercises that smoke tests don't

- **Real Temporal sandbox** — the workflow file imports `awaithumans/temporal`, which has to be sandbox-safe (no top-level fs / network)
- **Real signal round-trip** — `awaithumans` server → HMAC-signed webhook → `dispatchSignal` → Temporal client → workflow signal handler → `workflow.condition()` resolves
- **Cross-language wire compatibility** — wire format and signal naming match the Python adapter exactly. A Python receiver can signal a TS workflow and vice versa.
- **Workflow durability** — kill the worker mid-await and restart it; the workflow picks up where it left off when the signal arrives.

## Tunnel for non-localhost setups

If `awaithumans dev` runs anywhere except your local machine (Docker, hosted, Slack-OAuth-friendly ngrok), the server can't reach `http://localhost:8765`. Expose the callback receiver:

```sh
ngrok http 8765
# → https://<your-id>.ngrok.io
export AWAITHUMANS_CALLBACK_BASE=https://<your-id>.ngrok.io
npm run kickoff -- 250
```

The kickoff script bakes `AWAITHUMANS_CALLBACK_BASE` into the workflow input, which the workflow uses to construct the per-run callback URL (`<base>/awaithumans/callback?wf=<workflow_id>`).

## Common gotchas

| Symptom | Fix |
|---|---|
| `Couldn't find an admin token` | Start `awaithumans dev` first |
| `AWAITHUMANS_PAYLOAD_KEY is required` (callback server) | Export it from the same `awaithumans dev` payload key file |
| Workflow hangs forever | Callback receiver isn't running, or `AWAITHUMANS_CALLBACK_BASE` doesn't reach it |
| `[callback] rejected bad signature` | The two processes have different `PAYLOAD_KEY`s — make sure both read the same value |
| Workflow times out | Default timeout is 15 min; for testing, complete the task in the dashboard before that |
