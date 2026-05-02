# LangGraph × awaithumans — refund-approval agent

A LangGraph agent that pauses for human approval through awaithumans, then continues. Single-process: the script runs the graph and drives it through the human-in-the-loop dance.

## Architecture

```
┌──────────────────────────────┐  HTTP POST /api/tasks  ┌──────────────────────┐
│ refund_agent.py              │ ──────────────────────►│ awaithumans server   │
│  - graph: triage → review    │                        │ (awaithumans dev)    │
│         → process_refund     │                        │                      │
│  - drive_human_loop(graph,…) │   long-poll status     │ — human reviews ──►  │
│                              │ ──────────────────────►│ — completes task ──► │
│  ◄── interrupt / resume ──── │ ◄──────────────────────│                      │
└──────────────────────────────┘    response payload    └──────────────────────┘
```

Unlike the Temporal example, **no separate worker or callback server is needed**. LangGraph is library-style — the same script that defines the graph also drives it. The `drive_human_loop` helper handles the interrupt/resume cycle automatically.

## Run it locally

### 1. Boot the awaithumans server (separate window)

```bash
awaithumans dev
# Reads / generates: PAYLOAD_KEY, ADMIN_API_TOKEN, sqlite DB
# Writes a discovery file to ~/.awaithumans-dev.json
```

Open the printed `/setup?token=...` URL and create your operator user.

### 2. Install this example's deps

```bash
cd examples/langgraph
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

The `-e ../../packages/python[langgraph]` line installs the in-tree adapter — switch to `awaithumans[langgraph]>=0.1.0` after PyPI publish.

### 3. Run the agent

```bash
python refund_agent.py 250
```

You'll see:

```
INFO  Starting graph — open the dashboard at http://localhost:3001
INFO  Triage: customer=cus_demo amount=$250 score=0.42
```

Then the script pauses, waiting for the human.

### 4. Approve in the dashboard

Open `http://localhost:3001`, log in as the operator, find the **Approve $250 refund for cus_demo?** task, fill the form, hit submit.

The script's terminal prints:

```
INFO  Decision received: approved=True notes='looks legit'
INFO  Processed refund: refund-cus_demo-250
INFO  Graph completed: {'customer_id': 'cus_demo', 'amount_usd': 250, ...}
```

## How interrupt/resume works

LangGraph's `interrupt(value)` raises a `GraphInterrupt`. The graph stops at that node. The driver (in our case `drive_human_loop`) sees the interrupt, does its work, and resumes the graph by streaming `Command(resume=response)` — the node re-executes from the top, but this time `interrupt(...)` returns the resume value instead of raising.

That re-execution is important: any side effects you do BEFORE `await_human` will run twice. Move side effects after the `await_human` call, or wrap them in idempotency guards.

## Why this works under failure

- **Driver process dies during the await**: LangGraph's checkpointer (here `MemorySaver`, but typically SQLite/Postgres/Redis in production) persists the graph state. Re-running the script with the same `thread_id` resumes from the parked node. The deterministic `idempotency_key` means the awaithumans server returns the existing task — no duplicate ticket for the human.
- **awaithumans server restarts**: tasks are persisted; on restart the dashboard reconnects and the polling driver resumes its long-poll.
- **Human times out**: `drive_human_loop` raises `TaskTimeoutError`, propagating into your script. Catch it and decide what to do — retry with a different reviewer, escalate, or fail closed.

## Common gotchas

- **No checkpointer = no interrupts.** LangGraph requires a checkpointer to support `interrupt(...)`. The example uses `MemorySaver` for simplicity; production graphs should use a durable backend.
- **Side effects in the review node**: anything before `await_human(...)` runs twice (once before interrupt, once on resume). Move expensive or non-idempotent work to a separate node downstream.
- **Multiple `await_human` calls in one node**: each interrupts independently; LangGraph routes resume values by call order. Pass distinct `idempotency_key=` if the (task, payload) tuples might collide.
