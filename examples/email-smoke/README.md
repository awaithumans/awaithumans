# email-smoke

End-to-end smoke test for the email channel — driven from TypeScript so
the test exercises both the public TS SDK contract AND the Python server's
email path. No mocks; runs against a real `awaithumans dev` server.

## What it does

1. Creates an email sender identity using the `file` transport — emails
   are written to a tmp directory instead of being shipped through Resend
   or SMTP. Lets the test capture them deterministically.
2. Calls `awaitHuman` from the TS SDK with a single-Switch response
   schema and `notify=["email+<id>:..."]`. The TS SDK now synthesizes a
   `form_definition` from the Zod schema, so the email renderer emits
   Approve / Reject magic-link buttons (not the link-out fallback).
3. Polls the tmp dir for the captured email; asserts on its content
   (task title, payload), then parses out the Approve magic-link URL.
4. POSTs the magic-link URL — the public action endpoint completes the
   task with `approved=true` baked into the signed token.
5. `awaitHuman`'s long-poll resolves with the typed response. Asserts
   `approved === true`.

If any step fails, the test exits non-zero with the detail. The email
identity is cleaned up on both success and failure.

## Run it

In one terminal, start the dev server:

```sh
awaithumans dev
```

The first run generates a dev admin token at `~/.awaithumans/admin.token`.

In another terminal:

```sh
cd examples/email-smoke
npm install
export AWAITHUMANS_ADMIN_API_TOKEN="$(cat ~/.awaithumans/admin.token)"
npm start
```

Expected output:

```
→ email capture dir: /var/folders/.../awaithumans-smoke-XXXXXX
→ smoke against http://localhost:3001
→ created email identity 'smoke-...' (file transport)
→ captured email: subject="Review: Approve wire transfer (smoke test)" to=smoke-recipient@example.test
→ email body content checks: OK
→ magic-link URL: http://localhost:3001/api/channels/email/action/...
→ POSTed magic-link → 200
✓ smoke pass: TS SDK + email channel + magic-link round-trip
```

## Knobs

| Env var | Default | Notes |
|---|---|---|
| `AWAITHUMANS_URL` | `http://localhost:3001` | Override if your dev server is elsewhere (ngrok, separate host) |
| `AWAITHUMANS_ADMIN_API_TOKEN` | required | Bearer token for `/api/tasks` and `/api/channels/email/identities`. The dev server prints its path on first start |

## Troubleshooting

- **"AWAITHUMANS_ADMIN_API_TOKEN is required"** — start `awaithumans dev`
  first, then export the token from the path the CLI printed.
- **"Timed out waiting for email"** — the dev server's email transport may
  have rejected the route (unknown identity, wrong format). Check the dev
  server logs.
- **`awaitHuman` rejects with `TaskCreateError 403`** — your token doesn't
  match the server's `ADMIN_API_TOKEN`. Re-export it from the CLI's path.
- **`awaitHuman` rejects with `TaskTimeoutError`** — the magic-link click
  succeeded but the task didn't transition to completed. Inspect the task
  in the dashboard at `http://localhost:3001/`.

## What this catches that unit tests don't

- Wire-format drift between the TS SDK and Python server schemas
- The TS SDK's `extractForm` synthesizing a Switch shape the email
  renderer actually accepts (the magic-link decision tree only fires
  on a single Switch / small SingleSelect)
- The notify route parser accepting the `email+<identity>:<target>`
  syntax against a real DB row
- The email renderer actually emitting magic-link buttons for a
  synthesized FormDefinition
- The action endpoint completing the task without auth (signed token,
  no session)
- The TS SDK's `Authorization: Bearer` header reaching the server
- The TS SDK's poll loop resolving when the task completes via a
  non-SDK path (the magic-link POST happens out-of-band, just like a
  real human review would)
