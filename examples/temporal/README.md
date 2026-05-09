# Temporal × awaithumans — refund-approval example

A real Temporal workflow that pauses for a human approval through awaithumans, then continues.

This is the canonical durable-HITL pattern: the workflow's `await_human()` call gives Temporal back to the scheduler ("park me until a signal arrives"), the human reviews via the awaithumans dashboard / Slack / email, and a webhook from the awaithumans server signals the workflow back to life. Zero compute consumed while waiting; full Temporal durability if the worker restarts mid-await.

## Prerequisites

- Python 3.10+
- The Temporal CLI — `brew install temporal` on macOS; see [temporal.io/setup-cli](https://docs.temporal.io/cli) for Linux / Windows.
- `awaithumans dev` running locally (covered in step 2 below). The SDK auto-discovers the URL + admin token via `~/.awaithumans-dev.json` so you don't have to set env vars in your agent process.
- The Temporal adapter extra. This example's `requirements.txt` installs `awaithumans[temporal]` for you. If you're copying this code into your own project, run `pip install "awaithumans[temporal]"` — without the extra, the workflow fails to import `dispatch_signal`.

## Architecture

```
┌──────────────────┐  HTTP POST /api/tasks   ┌──────────────────────┐
│ Temporal worker  │ ─────────────────────►  │ awaithumans server   │
│ (refund_workflow)│                         │ (awaithumans dev)    │
│                  │                         │                      │
│ await_human()    │                         │ — human reviews ──►  │
│   parked         │                         │ — completes task ──► │
│                  │  webhook (signed)       │                      │
│                  │ ◄───────────────────────│                      │
└─────┬────────────┘                         └──────────────────────┘
      │ Temporal signal
      │ (via dispatch_signal)
┌─────▼────────────────┐
│ FastAPI receiver     │
│ (callback_server.py) │
└──────────────────────┘
```

Three processes:

| Process              | What it does                                  | Command                                |
|----------------------|-----------------------------------------------|----------------------------------------|
| awaithumans server   | Stores tasks, hosts dashboard, fires webhooks | `awaithumans dev`                      |
| Temporal worker      | Runs the workflow                             | `python refund_workflow.py worker`     |
| Callback receiver    | Converts webhooks → Temporal signals          | `uvicorn callback_server:app --port 8765` |

Plus a one-shot kickoff to start a workflow run: `python refund_workflow.py start 250`.

## Run it locally

### 1. Boot Temporal (separate window)

```bash
brew install temporal      # mac; see temporal.io/setup-cli for others
temporal server start-dev  # listens on localhost:7233 + UI at :8233
```

### 2. Boot the awaithumans server

```bash
awaithumans dev
# Reads / generates: PAYLOAD_KEY, ADMIN_API_TOKEN, sqlite DB
# Writes a discovery file to ~/.awaithumans-dev.json so the SDK
# auto-finds the URL + bearer token.
```

Open the printed `/setup?token=...` URL and create your operator user.

### 3. Install this example

```bash
cd examples/temporal
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

The `-e ../../packages/python[temporal]` line installs the in-tree adapter — switch to `awaithumans[temporal]>=0.1.0` after PyPI publish.

### 4. Tunnel the callback server (so the awaithumans server can reach it)

In dev with everything on `localhost`, you can skip the tunnel: `localhost:3001` (awaithumans) can reach `localhost:8765` (callback) directly. If your awaithumans server runs in Docker or on another host:

```bash
ngrok http 8765
export AWAITHUMANS_CALLBACK_BASE=https://<your-ngrok-id>.ngrok.io
```

### 5. Boot the worker + callback receiver

```bash
# Terminal 1
python refund_workflow.py worker

# Terminal 2
uvicorn callback_server:app --host 0.0.0.0 --port 8765
```

### 6. Kick off a workflow

```bash
# Terminal 3
python refund_workflow.py start 250
```

You'll see the workflow log "Started workflow id=…", then nothing — it's parked, waiting for the human.

### 7. Approve in the dashboard

Open `http://localhost:3001`, log in as the operator, find the **Approve $250 refund for cus_demo?** task, fill the form, hit submit.

The kickoff terminal will log the workflow result a second later:

```
Workflow result: {'refund_id': 'refund-xxxx', 'outcome': 'approved', 'notes': '…'}
```

## Why this works under failure

- **Worker dies during the await**: Temporal restarts the workflow; `await_human()` re-runs and re-registers the signal handler with the same idempotency key. The awaithumans server returns the existing task (idempotency dedup). When the human eventually completes, the signal fires on the live worker.
- **Callback server is down when the human submits**: the awaithumans server's outbound webhook fails-loudly in its logs but doesn't retry. The workflow times out at `timeout_seconds`, raises `TaskTimeoutError`, and the operator sees the abandoned task in the dashboard. (Post-launch: bounded retry on transient receiver failures.)
- **awaithumans server restarts**: tasks are persisted; on restart, the timeout scheduler resumes and the dashboard reconnects.

## Reading the code

- `refund_workflow.py` — the workflow + a downstream `process_refund` activity. The workflow imports `await_human` inside `workflow.unsafe.imports_passed_through()` so Temporal's sandbox lets it through.
- `callback_server.py` — a 60-line FastAPI app. `dispatch_signal()` does the security-critical bits (HMAC verify, parse, signal); the route is just web-framework glue.

## Common gotchas

- **`AWAITHUMANS_PAYLOAD_KEY` mismatch**: the HMAC key is HKDF-derived from this. If the awaithumans server and the callback receiver have different keys, signatures never verify and you'll see 401s in the receiver's logs. Use the same value on both processes.
- **`callback_url` not reachable**: the awaithumans server's logs show `Webhook delivery failed task=… url=…: …`. Most often this is a tunnel / firewall issue.
- **Duplicate idempotency key**: two `await_human` calls in the same workflow with the same `(task, payload)` get the same key by default. Pass `idempotency_key=` explicitly to disambiguate.
