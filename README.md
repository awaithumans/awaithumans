# awaithumans

**Your agents already await promises. Now they can await humans.**

The human layer for AI agents — open source, developer-native.

```python
from awaithumans import await_human
from pydantic import BaseModel

class Decision(BaseModel):
    approved: bool
    note: str | None = None

decision = await await_human(
    task="Approve refund request",
    payload_schema=RefundRequest,
    payload=RefundRequest(order_id="A-4721", amount_usd=180),
    response_schema=Decision,
    timeout_seconds=900,
)

if decision.approved:
    process_refund(...)
```

The agent waits on `decision` like it waits on any other Promise or Future.
A human gets notified (Slack, email, dashboard), reviews the request, and
submits a typed response. The agent resumes with the typed answer.

---

## The problem

Every production agent hits a wall where the model can't or shouldn't
proceed alone. Three distinct walls, each permanent:

- **Judgment.** The agent has the information but can't be trusted to
  decide. High liability, regulation, or consequence — KYC approvals,
  refund sign-offs, content moderation escalations. A human carries the
  accountability.
- **System-uncertainty.** The agent doesn't know the state of the world.
  The source of truth is in a bank dashboard, a partner system, a
  manual file. No model can close this gap. A human investigates and
  tells the agent what's true.
- **Embodiment.** The task requires a real person — signing, calling,
  picking something up, passing a CAPTCHA. Not a model problem.

Better models don't solve walls 2 and 3. `awaithumans` makes the call
to a human a first-class primitive instead of a pile of bespoke glue
per project.

---

## Quick start

**One terminal:**

```bash
pip install "awaithumans[server]"
awaithumans dev
```

You get the API server + dashboard on `http://localhost:3001`. On first
run it prints a setup URL; open it, create the initial operator
account, you're in.

**Another terminal:**

```python
# refund.py
from awaithumans import await_human_sync
from pydantic import BaseModel

class RefundRequest(BaseModel):
    order_id: str
    amount_usd: float

class Decision(BaseModel):
    approved: bool

decision = await_human_sync(
    task="Approve refund",
    payload_schema=RefundRequest,
    payload=RefundRequest(order_id="A-4721", amount_usd=180),
    response_schema=Decision,
    timeout_seconds=900,
)
print("approved" if decision.approved else "rejected")
```

```bash
python refund.py
```

Open the dashboard, click the task, approve it. The Python script
unblocks with `decision.approved == True`.

Full walkthrough: [`examples/quickstart/`](./examples/quickstart/).

---

## Complete tasks in Slack

Add `notify=["slack:#ops"]` and the task lands in the channel with a
"Claim this task" button. First clicker atomically wins; their
response form opens as a modal. Completing it unblocks the agent
just like the dashboard path.

```python
decision = await await_human(
    task="Approve refund",
    payload_schema=RefundRequest,
    payload=...,
    response_schema=Decision,
    notify=["slack:#ops"],
    timeout_seconds=900,
)
```

Works for direct messages too (`slack:@U01ABC234`) and email
(`email:reviewer@company.com`).

---

## Durable mode

When your agent runs inside a workflow engine, you don't want a
long-poll hanging on the orchestrator's thread for 15 minutes. The
Temporal and LangGraph adapters hand the wait to the engine itself:

**Temporal** — signal-based suspend + callback:

```python
from awaithumans.adapters.temporal import await_human_temporal

decision = await await_human_temporal(
    task="Approve refund",
    payload_schema=RefundRequest,
    payload=...,
    response_schema=Decision,
    timeout_seconds=900,
)
```

**LangGraph** — interrupt/resume:

```python
from awaithumans.adapters.langgraph import await_human_langgraph
```

Same `await_human` shape, same typed response. The adapter just
changes how the wait is orchestrated.

---

## AI verification

Ask an AI to pre-check the human's work before the agent trusts it.
Catches the "human clicked approve without reading" case:

```python
from awaithumans.verifiers.claude import verify_with_claude

decision = await await_human(
    task="Approve refund",
    payload_schema=RefundRequest,
    payload=...,
    response_schema=Decision,
    verifier=verify_with_claude(
        instructions="Reject if the note contradicts the approval.",
        max_attempts=2,
    ),
)
```

The verifier runs after each human submission. If it fails, the task
is re-sent to the human with the verifier's reason attached.

---

## TypeScript

```bash
npm install awaithumans
```

```ts
import { awaitHuman } from "awaithumans";
import { z } from "zod";

const RefundRequest = z.object({
  orderId: z.string(),
  amountUsd: z.number(),
});

const Decision = z.object({
  approved: z.boolean(),
});

const decision = await awaitHuman({
  task: "Approve refund",
  payloadSchema: RefundRequest,
  payload: { orderId: "A-4721", amountUsd: 180 },
  responseSchema: Decision,
  timeoutMs: 900_000,
});
```

Full walkthrough: [`examples/quickstart-ts/`](./examples/quickstart-ts/).

The server + dashboard are Python — TypeScript runs `npx awaithumans
dev` (via [uv](https://astral.sh/uv)) so you never touch a Python env.

---

## Self-hosted

```bash
docker run -p 3001:3001 ghcr.io/awaithumans/awaithumans:latest
```

Or `docker compose up` with the included `docker-compose.yml`
(optional Postgres block inside). Backs everything — API, dashboard,
channels — from one image.

---

## Architecture

- **Core primitive:** one function, `await_human()` / `awaitHuman()`,
  typed-in-typed-out.
- **Task store:** SQLite in dev, Postgres in prod. Idempotency keys,
  atomic state transitions, audit trail.
- **Channels:** Slack + email today. Plug in your own by implementing
  a small interface (`server/channels/`).
- **Verifiers:** Claude today, any provider is a one-file adapter.
- **Router:** least-recently-assigned over a user directory with
  free-form `role`/`access_level`/`pool` labels.
- **Task-type handlers:** forms auto-generated from your Pydantic /
  Zod schema, rendered per channel (Slack Block Kit, email, web form).

Every customization flows through one of these four buckets. That's
the entire extension surface.

---

## Documentation

- **Quickstart:** [`examples/quickstart/`](./examples/quickstart/)
- **Full docs:** [awaithumans.dev](https://awaithumans.dev)
- **Contributing:** [`CONTRIBUTING.md`](./CONTRIBUTING.md)
- **Security policy:** [`SECURITY.md`](./SECURITY.md)

---

## Packages

| Package | Registry | License |
|---|---|---|
| `awaithumans` (Python SDK + server + CLI + dashboard) | PyPI | Apache 2.0 |
| `awaithumans` (TypeScript SDK) | npm | Apache 2.0 |
| `ghcr.io/awaithumans/awaithumans` (container) | GHCR | Apache 2.0 |

**License:** [Apache License 2.0](LICENSE). Permissive, OSI-approved,
with an explicit patent grant. Use it in proprietary stacks, fork it,
ship it inside paid products — no fee, no contact required. The only
thing the license asks is that you preserve the notice and don't use
the project's trademarks without permission.

---

## Status

**Pre-launch.** Public launch: **May 12, 2026**.

If you found this before then and things are rough — welcome early!
File issues, open PRs, say hi in [Discussions](https://github.com/awaithumans/awaithumans/discussions).
