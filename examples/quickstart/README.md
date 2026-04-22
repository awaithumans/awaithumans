# Quickstart

The smallest thing that proves `awaithumans` works end-to-end: an
agent asks a human to approve a refund, the human clicks a button,
the agent gets the typed response back.

## Setup

```bash
pip install "awaithumans[server]"
```

## Run

**Terminal 1** — the server + dashboard:

```bash
awaithumans dev
```

You should see:

```
Ready — waiting for tasks...
Dashboard at http://0.0.0.0:3001
```

**Terminal 2** — the example agent:

```bash
python refund.py
```

You should see:

```
→ creating task on the awaithumans server...
  Open http://localhost:3001 to review.
```

## What to do

1. Open <http://localhost:3001>. The task appears in the queue:
   **“Approve refund request”**.
2. Click the row. The detail view shows the request (order, customer,
   amount, reason) and a form with two fields — **Approve?** (toggle)
   and **Note to customer** (textarea).
3. Fill it in. Click **Submit response**.

Terminal 2 unblocks and prints:

```
✓ Refund approved. Note: Issuing refund immediately.
```

## What the code looks like

```python
from awaithumans import await_human_sync
from pydantic import BaseModel


class RefundRequest(BaseModel):
    order_id: str
    customer: str
    amount_usd: float
    reason: str


class Decision(BaseModel):
    approved: bool
    note: str | None = None


decision = await_human_sync(
    task="Approve refund request",
    payload_schema=RefundRequest,
    payload=RefundRequest(order_id="A-4721", customer="...", amount_usd=180, reason="..."),
    response_schema=Decision,
    timeout_seconds=900,
)

if decision.approved:
    ...
```

Pydantic models on both sides: the `payload_schema` drives what the
human sees, the `response_schema` drives the form they fill out, and
your agent gets the typed `Decision` back. No JSON-twiddling.

## Next steps

- **Async version:** use `await_human` (instead of `await_human_sync`)
  inside an async agent loop.
- **Send to Slack or email:** add `notify=["slack:#ops"]` or
  `notify=["email:reviewer@company.com"]`. Needs the channel
  configured on the server — see [docs](https://awaithumans.dev/docs).
- **Durable workflows:** use the Temporal or LangGraph adapter so
  `await_human()` survives process restarts. Import from
  `awaithumans.adapters.temporal` or `awaithumans.adapters.langgraph`.
- **TypeScript:** the same flow in Node —
  [`examples/quickstart-ts/`](../quickstart-ts/).
