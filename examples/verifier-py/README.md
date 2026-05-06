# Verifier example (Python)

Smallest end-to-end demo of `awaithumans` AI verification: a refund
decision is gated by a Claude verifier before the agent unblocks.

The verifier runs **server-side** — this example just attaches a
`VerifierConfig` to the `await_human` call. The server reads
`ANTHROPIC_API_KEY` and runs the LLM check against the human's
submission.

Mirrors [`../verifier/`](../verifier/) (TypeScript).

## Prerequisites

- Python 3.10+
- A Claude API key exported in the **server's** shell as
  `ANTHROPIC_API_KEY` — the verifier runs server-side.

## Run

**Terminal 1** — the server (must see your API key):

```bash
export ANTHROPIC_API_KEY=sk-ant-...
pip install "awaithumans[server,verifier-claude]"
awaithumans dev
```

**Terminal 2** — this example agent:

```bash
pip install -r requirements.txt
python refund.py
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
| **Exhaust** | Submit bad reasons 3×in a row | After `max_attempts` → task VERIFICATION_EXHAUSTED → script raises `VerificationExhaustedError` |

The dashboard shows the rejection text from the verifier on each
failed attempt — that text comes straight from the LLM and is what
the human sees in the UI.

## What the code looks like

```python
from awaithumans import await_human_sync
from awaithumans.verifiers.claude import claude_verifier

decision = await_human_sync(
    task="Approve refund (verified)",
    payload_schema=RefundRequest,
    payload=RefundRequest(...),
    response_schema=Decision,
    timeout_seconds=900,
    verifier=claude_verifier(
        instructions="...quality gate prompt...",
        max_attempts=3,
    ),
)
```

That's the whole verifier integration — one extra kwarg.

## Next steps

- Swap providers: `awaithumans.verifiers.openai`, `.gemini`,
  `.azure_openai`. Same shape; different API key env var.
- Combine with `notify=["slack:#ops"]` — the verifier still runs no
  matter which channel the human used to submit.
- TypeScript version: [`../verifier/`](../verifier/).
