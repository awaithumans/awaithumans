# awaithumans

**Your agents already await promises. Now they can await humans.**

The human layer for AI agents — open source, developer-native. A single
primitive (`awaitHuman`) your agent can call when the model can't or
shouldn't proceed alone. A human gets notified (Slack, email, or
dashboard), reviews the request, submits a typed response, and your
agent resumes.

```ts
import { awaitHuman } from "awaithumans";
import { z } from "zod";

const RefundRequest = z.object({
  orderId: z.string(),
  amountUsd: z.number(),
});

const Decision = z.object({
  approved: z.boolean(),
  note: z.string().optional(),
});

const decision = await awaitHuman({
  task: "Approve refund request",
  payloadSchema: RefundRequest,
  payload: { orderId: "A-4721", amountUsd: 180 },
  responseSchema: Decision,
  timeoutMs: 900_000,
});

if (decision.approved) {
  await processRefund(...);
}
```

---

## Install

```bash
npm install awaithumans
# or
pnpm add awaithumans
# or
bun add awaithumans
```

Works in Node 20+, Bun, Deno, and edge runtimes (Cloudflare Workers,
Vercel Edge). No `node:*` imports.

---

## Run the server

The awaithumans server (which handles task storage, Slack/email
channels, and hosts the review dashboard) is written in Python. As a
TypeScript developer you don't have to touch a Python environment —
the npm CLI wraps it:

```bash
npx awaithumans dev
```

Under the hood this uses [uv](https://astral.sh/uv) to fetch + run the
Python server on demand. Install uv once:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh   # unix
powershell -c "irm https://astral.sh/uv/install.ps1 | iex"  # windows
```

First run prints a setup URL. Open it, create the operator account,
you're in. The dashboard is at `http://localhost:3001`.

Prefer Docker? `docker run -p 3001:3001 ghcr.io/awaithumans/awaithumans:latest`.

---

## Durable workflows

When your agent runs inside Temporal or LangGraph, you don't want the
wait sitting on an orchestrator thread for 15 minutes:

```ts
// Temporal — signal-based suspend + callback
import { awaitHuman } from "awaithumans/temporal";

// LangGraph — interrupt/resume
import { awaitHuman } from "awaithumans/langgraph";
```

Same `awaitHuman` shape, same typed response. The adapter just
changes how the wait is orchestrated.

---

## Testing

An in-memory mock client so your agent tests don't need a running
server:

```ts
import { createTestClient } from "awaithumans/testing";

const client = createTestClient();

// Drive the human's response programmatically.
client.onAwait((task) => ({ approved: true, note: "looks good" }));
```

---

## Documentation

- **Repository:** [github.com/awaithumans/awaithumans](https://github.com/awaithumans/awaithumans)
- **Full docs:** [awaithumans.dev](https://awaithumans.dev)
- **Quickstart:** [`examples/quickstart-ts/`](https://github.com/awaithumans/awaithumans/tree/main/examples/quickstart-ts)
- **Changelog:** [`CHANGELOG.md`](https://github.com/awaithumans/awaithumans/blob/main/CHANGELOG.md)

---

## License

MIT. The TypeScript SDK and all adapter subpath exports are MIT.

The server + dashboard (separately distributed, Python) are
[Elastic License v2](https://www.elastic.co/licensing/elastic-license)
— fully self-hostable for your own organization. See the
[repo README](https://github.com/awaithumans/awaithumans#packages)
for the per-file breakdown.
