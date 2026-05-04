# Slack-native refund review

The whole human-in-the-loop happens inside Slack. The operator never opens the dashboard.

This is the canonical "what does Slack-native really mean?" demo. Three Slack channel features used together:

1. **Broadcast claim** — `notify=["slack:#approvals"]` posts to a channel with a Claim button. First clicker wins atomically.
2. **Modal review** — claim opens a Block Kit modal with the form, auto-generated from the response schema.
3. **NL thread replies** — instead of clicking through the modal, the reviewer can reply "approve, looks legit" in the thread. The verifier parses it into the structured response.

Anyone in `#approvals` can complete the task. The agent gets a typed `RefundDecision` either way.

## What you'll see in Slack

```
[#approvals]
bot:  🤖 Approve $250 refund for cus_demo?
      Customer: cus_demo  ·  Amount: $250  ·  Reason: Duplicate charge

      [ Claim this task ]                          ← anyone in channel can click

(alice clicks Claim)

bot:  ✓ Claimed by @alice                          ← message updates,
                                                     button vanishes for everyone

→ Modal pops for alice with the approve/reject form.
   OR
   alice replies in the thread:
     @alice: approve, looks legit — duplicate confirmed by Stripe
   …and the verifier turns that into { approved: true, notes: "duplicate confirmed by Stripe" }.
```

The script's terminal prints the typed decision a moment later.

## Run it locally

You need three terminals.

### 1. Boot the awaithumans server

```bash
awaithumans dev
```

Open the printed `/setup?token=...` URL, create your operator account.

### 2. Tunnel for Slack interactivity

Slack POSTs to your server when someone clicks Claim or submits the modal. For local dev, expose port 3001 publicly:

```bash
ngrok http 3001
# Copy the https URL — you'll need it for the Slack app config below.
```

If you have a static public URL (e.g. cloudflared tunnel, hosted dev box), use that instead.

### 3. Create a Slack app (one-time)

Go to [api.slack.com/apps](https://api.slack.com/apps) → **Create New App** → **From manifest**. Paste:

```yaml
display_information:
  name: Await Humans
features:
  bot_user:
    display_name: Await Humans
    always_online: true
oauth_config:
  scopes:
    bot:
      - chat:write
      - im:write
      - channels:read
      - groups:read
      - users:read
      - files:write
      - files:read
settings:
  interactivity:
    is_enabled: true
    request_url: https://YOUR-NGROK-URL.ngrok.io/api/channels/slack/interactions
  org_deploy_enabled: false
  socket_mode_enabled: false
```

Replace `YOUR-NGROK-URL.ngrok.io` with the URL from step 2.

After creating:
- Click **Install to Workspace**, approve.
- Copy the **Bot User OAuth Token** (`xoxb-...`) from OAuth & Permissions.
- Copy the **Signing Secret** from Basic Information.

### 4. Wire the tokens into the awaithumans server

Stop the server from step 1 (Ctrl-C). Restart with the tokens set:

```bash
export AWAITHUMANS_SLACK_BOT_TOKEN=xoxb-...
export AWAITHUMANS_SLACK_SIGNING_SECRET=...
export AWAITHUMANS_PUBLIC_URL=https://YOUR-NGROK-URL.ngrok.io  # so dashboard URLs match the tunnel

# Optional — enables NL-thread-reply parsing
export ANTHROPIC_API_KEY=sk-ant-...

awaithumans dev
```

### 5. Add yourself to the directory

The Slack member trying to complete the task needs to be in the awaithumans user directory.

Open the dashboard (`http://localhost:3001`), Settings → Users → Add User. Pick your Slack workspace + user from the dropdowns. Save. (One-time; subsequent runs skip this.)

### 6. Invite the bot to `#approvals`

In Slack, in `#approvals`:

```
/invite @Await Humans
```

(Or whatever channel you want — set `AWAITHUMANS_DEMO_CHANNEL=#your-channel` to override the default.)

### 7. Run the example

```bash
cd examples/slack-native
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python refund_review.py 250
```

The bot posts in `#approvals`. Click Claim, fill the modal (or reply NL in the thread), watch the script print the decision.

## What the script does

```python
# refund_review.py — abridged

decision: RefundDecision = await_human_sync(
    task=f"Approve ${amount_usd} refund for {customer_id}?",
    payload_schema=RefundPayload,
    payload=RefundPayload(...),
    response_schema=RefundDecision,
    timeout_seconds=15 * 60,
    notify=["slack:#approvals"],   # ← the only Slack-specific line
    verifier=_verifier_or_none(),
)

if decision.approved:
    process_refund(...)
```

That's the whole interface. The `notify=` string is what makes it Slack-native; the rest is the same `await_human` you'd use in any agent.

## Why broadcast + claim instead of direct DM?

You could have used `notify=["slack:@alice"]` to DM Alice directly (or `slack:alice@acme.com`, or `slack:@U_ALICE_ID` — all three resolve to the same person). We picked broadcast for the demo because:

- It shows what makes Slack-native compelling: anyone watching the channel can pick up the task. No need to know up-front who's online or available.
- The atomic-claim model is easy to demo and easy to reason about — first clicker wins, message updates so others stop trying.
- It generalizes to any operations queue (`#oncall`, `#ops-reviews`, etc.) without requiring direct user assignment.

For high-volume queues with specific assignees, mix the patterns: route by role / pool (see [`docs/routing/overview`](https://awaithumans.dev/docs/routing/overview)) and let `notify` broadcast. The router stamps the assignee; the broadcast notifies the whole channel; the claim path validates the clicker against the directory.

## Why have an NL fallback at all?

Two reasons:

- **Reviewer-on-mobile.** Slack's mobile modal works but it's clunky. Replying "approve, looks ok" with a thumb is faster.
- **Async-first cultures.** Some teams run reviews entirely in threads — the modal is the formal path; the thread is where the actual conversation happens. Allowing NL replies means the conversation IS the audit trail.

The verifier (Claude Sonnet by default) handles the NL parsing in the same call that quality-checks the response. One LLM call does both jobs.

## Authorization

The Slack channel handler validates the submitter against the directory:
- Must be in the user directory (Settings → Users) AND active
- Must be either the task's assignee OR an operator

For broadcast-claim tasks (`assign_to=None`), the first claimer becomes the assignee. The check is "must be in the directory" — anyone who's been added to the awaithumans server's user list can claim.

For direct-assigned tasks (`assign_to="alice@..."`), only Alice or an operator can claim and submit.

The audit log records `completed_by_email` as Alice's directory email (NOT her Slack `username`), so attribution stays consistent across Slack and dashboard completions.

## Common gotchas

- **Bot not in channel.** "no_channel" or "not_in_channel" errors → invite the bot via `/invite`.
- **Slack signature verification fails.** `AWAITHUMANS_SLACK_SIGNING_SECRET` must match the value in your Slack app's Basic Information page exactly.
- **Modal opens but submission 401s.** The submitter isn't in the awaithumans user directory. Add them via Settings → Users.
- **Tunnel URL changed.** ngrok free-tier URLs rotate. Re-paste into the Slack app's `request_url` and restart the server with the new `AWAITHUMANS_PUBLIC_URL`.
- **NL replies don't parse.** `ANTHROPIC_API_KEY` not set on the server. The script logs a warning at startup if so.
