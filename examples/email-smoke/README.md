# email-smoke

End-to-end smoke test for the email channel — driven from TypeScript so
the test exercises both the public TS SDK contract AND the Python server's
email path. No mocks; runs against a real `awaithumans dev` server.

## What it does

1. Creates an email sender identity using the `file` transport — emails
   are written to a tmp directory instead of being shipped through Resend
   or SMTP. Lets the test capture them deterministically.
2. Calls `awaitHuman` from the TS SDK with `notify=["email+<id>:..."]`,
   then immediately starts polling the tmp dir for the rendered email.
3. Asserts on the captured email's content (task title, payload fields,
   dashboard link). Confirms the renderer didn't regress on a known good
   shape.
4. Completes the task via the admin API; `awaitHuman`'s long-poll
   resolves with the typed response. Asserts `approved === true`.

If any step fails, the test exits non-zero with the detail. The email
identity is cleaned up on both success and failure.

### Why admin-API completion instead of clicking the magic-link button?

The TS SDK doesn't yet synthesize a `form_definition` from a Zod schema
— Python has `extract_form` (Pydantic-driven), the TS port is
post-launch work. Without that, the email renderer falls back to a
"Review in dashboard" link-out and never emits Approve/Reject magic-link
buttons. Once form synthesis lands in the TS SDK, this script will
switch to clicking the button instead. The magic-link click path itself
has full Python coverage in `tests/email/`.

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
→ resolved task_id=...
→ completed task ... via admin API
✓ smoke pass: TS SDK created task → email captured → SDK polled → resolved
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
- The notify route parser accepting the `email+<identity>:<target>`
  syntax against a real DB row
- The email renderer actually rendering against a real task — task
  title, payload table, dashboard link
- The TS SDK's `Authorization: Bearer` header reaching the server
- The TS SDK's poll loop resolving when the task completes via a
  non-SDK path (the admin completion happens out-of-band, just like
  a real human review would)
