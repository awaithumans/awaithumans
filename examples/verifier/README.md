# Verifier example (TypeScript)

Smallest end-to-end demo of `awaithumans` AI verification: a refund
decision is gated by a Claude verifier before the agent unblocks.

The verifier runs **server-side** — this example just attaches a
verifier config to the `awaitHuman` call. The server reads
`ANTHROPIC_API_KEY` and runs the LLM check against the human's
submission.

Mirrors [`../verifier-py/`](../verifier-py/) (Python).

## Prerequisites

- Node 20+
- A Claude API key exported in the **server's** shell as
  `ANTHROPIC_API_KEY` — the verifier runs server-side.

## Run

**Terminal 1** — the server (must see your API key):

```bash
export ANTHROPIC_API_KEY=sk-ant-...
npx awaithumans dev
```

**Terminal 2** — this example agent:

```bash
npm install
npm start
```

You should see:

```
→ creating refund task with a Claude verifier attached...
  Open http://localhost:3001 to review.
```

## What to test

Open <http://localhost:3001> and walk the three verifier paths:

| Goal | Submit this | Result |
|---|---|---|
| **Pass** | Approve, reason references *damage / policy / evidence* | Verifier passes → task COMPLETED → script unblocks |
| **Reject + retry** | Approve, reason `"ok"` | Verifier rejects → task REJECTED (non-terminal) → resubmit |
| **Exhaust** | Submit bad reasons 3× in a row | After `max_attempts` → task VERIFICATION_EXHAUSTED → script throws `VerificationExhaustedError` |

The dashboard shows the rejection text from the verifier on each
failed attempt — that text comes straight from the LLM and is what
the human sees in the UI.

## What the code looks like

```ts
import { awaitHuman } from "awaithumans";

const decision = await awaitHuman({
  task: "Approve refund (verified)",
  payloadSchema: RefundRequest,
  payload: { ... },
  responseSchema: Decision,
  timeoutMs: 900_000,
  verifier: {
    provider: "claude",
    model: "claude-sonnet-4-20250514",
    instructions: "...quality gate prompt...",
    maxAttempts: 3,
    apiKeyEnv: "ANTHROPIC_API_KEY",
  },
});
```

The SDK translates the camelCase config into the server's snake_case
`verifier_config` wire shape for you.

## Next steps

- Swap providers: change `provider` to `"openai"`, `"gemini"`, or
  `"azure_openai"`. Each provider reads a different API key env var.
- Combine with `notify: ["slack:#ops"]` — the verifier still runs no
  matter which channel the human used to submit.
- Python version: [`../verifier-py/`](../verifier-py/).
