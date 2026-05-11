# awaithumans

**Your agents already await promises. Now they can await humans.**

The human layer for AI agents — open source, developer-native. A single
primitive (`await_human`) your agent can call when the model can't or
shouldn't proceed alone. A human gets notified (Slack, email, or
dashboard), reviews the request, submits a typed response, and your
agent resumes.

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

---

## Install

```bash
pip install awaithumans                    # SDK only — lightweight HTTP client
pip install "awaithumans[server]"          # SDK + server + CLI + bundled dashboard
```

Extras for specific adapters:

```bash
pip install "awaithumans[temporal]"        # Temporal workflow adapter
pip install "awaithumans[langgraph]"       # LangGraph interrupt/resume adapter
pip install "awaithumans[verifier-claude]" # AI verification via Claude
```

Extras stack — install multiple in one command:

```bash
pip install "awaithumans[server,temporal,verifier-claude]"
```

---

## Quick start

```bash
pip install "awaithumans[server]"
awaithumans dev
```

First run prints a setup URL. Open it, create the operator account,
you're in. The dashboard runs on `http://localhost:3001`.

Then your agent:

```python
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
```

`await_human_sync` is the blocking form. For async agents use
`await_human` directly.

---

## Routing

Route tasks to people (not channels) via `assign_to`:

```python
decision = await await_human(
    task="...",
    assign_to={"role": "kyc-reviewer", "access_level": "senior"},
    ...,
)
```

The server picks the least-recently-assigned active user matching the
filter — fair distribution across your team. Manage the user directory
via the dashboard's Settings page or the CLI:

```bash
awaithumans add-user --email alice@company.com --role kyc-reviewer --access-level senior
awaithumans list-users
awaithumans remove-user alice@company.com
awaithumans set-password alice@company.com
```

---

## Notifications

```python
notify=["slack:#ops", "email:reviewer@company.com"]
```

Slack channel broadcasts post a "Claim this task" button; first
clicker atomically wins. Direct messages and emails go straight to
the recipient.

---

## Durable workflows

```python
from awaithumans.adapters.temporal import await_human_temporal
from awaithumans.adapters.langgraph import await_human_langgraph
```

Same `await_human` shape. The adapter hands the wait to the engine
(Temporal signal / LangGraph interrupt) so the orchestrator isn't
holding a connection open for 15 minutes.

---

## AI verification

```python
from awaithumans.verifiers.claude import verify_with_claude

decision = await await_human(
    task="...",
    verifier=verify_with_claude(
        instructions="Reject if the note contradicts the approval.",
        max_attempts=2,
    ),
)
```

The verifier runs after each human submission; failures re-send to the
human with the reason attached.

---

## Documentation

- **Repository:** [github.com/awaithumans/awaithumans](https://github.com/awaithumans/awaithumans)
- **Full docs:** [awaithumans.dev](https://awaithumans.dev)
- **Examples:** [`examples/quickstart/`](https://github.com/awaithumans/awaithumans/tree/main/examples/quickstart) and [`examples/quickstart-ts/`](https://github.com/awaithumans/awaithumans/tree/main/examples/quickstart-ts)
- **Changelog:** [`CHANGELOG.md`](https://github.com/awaithumans/awaithumans/blob/main/CHANGELOG.md)

---

## License

[Apache License 2.0](https://github.com/awaithumans/awaithumans/blob/main/LICENSE)
across the whole package — SDK, server, dashboard, adapters, channels.
Permissive, OSI-approved, with an explicit patent grant. Use it in
proprietary stacks, fork it, ship it inside paid products.
