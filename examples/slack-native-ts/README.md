# slack-native-ts

TypeScript counterpart of [`../slack-native/`](../slack-native/) (Python).
Same flow, same shape — different SDK.

A small script that creates a wire-transfer approval task, sends it
as a Slack DM to a tagged user (`@TA` by default), and prints the
response when they decide.

## What runs

1. The TS SDK creates a task with `notify=["slack:@TA"]`.
2. The server resolves `@TA` against the directory (implicit-
   assignee derivation pins TA as `assigned_to_user_id`), then DMs
   them via the Slack channel.
3. TA sees the DM with two buttons:
   - **Approve in Slack** — opens the Block-Kit modal in place
   - **Open in Dashboard** — signed handoff URL (works even if TA
     has no email/password)
4. TA submits via either path. The Slack message updates to
   "Completed by @TA" with no buttons.
5. This script's `awaitHuman` resolves with the typed response.

## Prerequisites

- **`awaithumans dev` running** in another terminal. The TS SDK
  reads its discovery file for URL + admin token, so no env-var
  dance is needed.
- **Slack app linked + workspace OAuth completed** — one-time setup,
  see [`examples/slack-native/README.md`](../slack-native/README.md)
  for the full Slack-side configuration. ngrok required for OAuth /
  interactivity callbacks.
- **User in the directory.** In the dashboard's Users page, click
  "Add user", paste the Slack handle (`@TA`), pick the workspace
  from the dropdown. Display name auto-fills.

## Run

```sh
cd examples/slack-native-ts
npm install
npm start
```

Expected output:

```
→ creating task — notify=slack:@TA
  transfer_id=WT-MOUI...
[blocks until TA decides in Slack]

✓ Approved by @TA
  full response: {"approved":true}
```

## Change the Slack handle

By default the script tags `@TA`. Edit `wire-transfer.ts`:

```ts
const SLACK_HANDLE = "TA";  // ← change to whatever handle you added
```

## What this exercises

- TS SDK creates a task with Slack notify entry
- Server-side implicit-assignee derivation (`@TA` → directory user
  with that Slack handle → set as `assigned_to_user_id`)
- Slack notification: DM sent with Approve/Open buttons
- Slack interactivity: modal opens, view_submission completes the
  task, message updates to "Completed by @TA"
- TS SDK long-poll resolves on out-of-band completion

If any of the above breaks, the Slack-channel coverage hasn't
regressed but the contract between TS SDK and server has — start
with `pytest tests/slack/` then check the dashboard's audit log.

## Why no automated smoke for Slack (vs email)?

The email path has a public, signed-token endpoint
(`/api/channels/email/action/<token>`) that any HTTP client can
POST to. Slack's interactivity endpoints sign requests against a
shared secret per workspace and route through Slack's own
servers — not feasible to drive from a local script without
spinning up a real Slack app.

This example is a manual checklist for "does the Slack flow work
end-to-end from TypeScript." Run it, click around, watch the dash.
