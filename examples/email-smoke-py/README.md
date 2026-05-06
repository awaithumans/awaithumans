# email-smoke-py

End-to-end email-channel smoke test driven from the **Python** SDK —
the language-parity counterpart of [`../email-smoke/`](../email-smoke/)
(which drives the same test from TypeScript).

Both scripts do the same thing:

1. Configure an email sender identity backed by the `file` transport
   (writes one JSON per email into a tmp dir, captured by the test).
2. Call the SDK's `await_human` / `awaitHuman` with a single-boolean
   response schema and `notify=["email+<id>:..."]`. The SDK
   synthesizes a Switch primitive in `form_definition`, which is what
   the email renderer needs to emit Approve / Reject magic-link
   buttons (anything else falls back to a "Review in dashboard" link-
   out).
3. Poll the tmp dir for the rendered email, parse the Approve URL out
   of the body, then POST to it. The action endpoint completes the
   task with the value baked into the signed token.
4. Wait for `await_human` to resolve. Assert `approved == True`.

If any step fails the test exits non-zero. The email identity is
cleaned up on both success and failure.

## Run it

In one terminal, start the dev server:

```sh
awaithumans dev
```

The first run generates a dev admin token at `~/.awaithumans/admin.token`
(or `<cwd>/.awaithumans/admin.token`, depending on where you ran
`awaithumans dev`).

In another terminal:

```sh
cd examples/email-smoke-py
pip install -r requirements.txt
export AWAITHUMANS_ADMIN_API_TOKEN="$(cat ~/.awaithumans/admin.token)"
python smoke.py
```

Expected output:

```
→ email capture dir: /var/folders/.../awaithumans-py-smoke-XXXXXX
→ smoke against http://localhost:3001
→ created email identity 'smoke-py-...' (file transport)
→ captured email: subject="Review: Approve wire transfer (smoke test)" to=smoke-recipient@example.test
→ email body content checks: OK
→ magic-link URL: http://localhost:3001/api/channels/email/action/...
→ POSTed magic-link → 200
✓ smoke pass: Python SDK + email channel + magic-link round-trip
```

## Knobs

| Env var | Default | Notes |
|---|---|---|
| `AWAITHUMANS_URL` | `http://localhost:3001` | Override if your dev server is elsewhere |
| `AWAITHUMANS_ADMIN_API_TOKEN` | required | Bearer token for `/api/tasks` and `/api/channels/email/identities` |

## What this catches that unit tests don't

- `extract_form` synthesizing a Switch shape the email renderer
  actually accepts (the magic-link decision tree only fires on a
  single Switch / small SingleSelect)
- The notify route parser accepting `email+<identity>:<target>`
  against a real DB row
- The email renderer emitting magic-link buttons against a real task
- The action endpoint completing the task without auth (signed
  token, not session-protected)
- The Python SDK's poll loop resolving when the task completes via a
  non-SDK path (the magic-link POST happens out-of-band, just like a
  real human review would)
