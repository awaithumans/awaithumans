# email-end-to-end-py

Python counterpart of [`../email-end-to-end/`](../email-end-to-end/)
(TypeScript). Same flow, same shape — different SDK.

A small script that creates a real-delivery email task, waits for
you to click the Approve button in your actual inbox, and prints
the response when the click lands.

## Prerequisites

- **`awaithumans dev` running** in another terminal. The Python
  SDK reads its discovery file for URL + admin token, so no
  env-var dance is needed.
- **A real email transport** — pick one:
  - **Resend** (recommended) — a free account + API key
  - **SMTP** — Gmail App Password / Hostinger mailbox / AWS SES
    SMTP credentials / Mailgun SMTP / etc.

## Option A — Resend (5 minutes)

1. Sign up at resend.com (free tier is plenty).
2. **API Keys → Create API Key** — copy the `re_…` value.
3. Run:
   ```sh
   cd examples/email-end-to-end-py
   pip install -r requirements.txt
   AWAITHUMANS_TEST_TRANSPORT=resend \
     RESEND_API_KEY=re_xxxxxxxxxxxxxxxxxxxxxxxx \
     RECIPIENT_EMAIL=you@example.com \
     python send.py
   ```
4. Check your inbox — should land within ~2 seconds. Click
   **Approve**.
5. Script prints `✓ Approved — task completed end-to-end via real
   email` and exits.

`onboarding@resend.dev` is the default sender (no domain
verification needed). Override with `FROM_EMAIL=alerts@yourdomain.com`
once you've verified a domain in Resend.

## Option B — SMTP (Gmail App Password)

1. Enable 2FA on the Google account
   (https://myaccount.google.com/security).
2. Generate an App Password
   (https://myaccount.google.com/apppasswords) — pick "Mail" →
   "Other (custom name)" → name it `awaithumans-dev`.
3. Run:
   ```sh
   AWAITHUMANS_TEST_TRANSPORT=smtp \
     SMTP_HOST=smtp.gmail.com SMTP_PORT=587 \
     SMTP_USER=you@gmail.com SMTP_PASSWORD="<the 16-char app password>" \
     FROM_EMAIL=you@gmail.com \
     RECIPIENT_EMAIL=you@gmail.com \
     python send.py
   ```

## Option C — Hostinger Mail

Hostinger uses port 465 with implicit TLS (SSL on connect). The
script auto-flips between SSL and STARTTLS based on the port — no
extra flag.

1. **Find your mailbox credentials** in Hostinger hPanel:
   - **Emails → pick the mailbox → Connect Apps & Devices**
   - **SMTP host**: `smtp.hostinger.com`
   - **SMTP port**: `465` (SSL — preferred) or `587` (STARTTLS)
   - **Username**: full email address (`you@yourdomain.com`)
   - **Password**: the mailbox password (NOT your Hostinger
     account password; reset via hPanel if you forget)
2. Run:
   ```sh
   AWAITHUMANS_TEST_TRANSPORT=smtp \
     SMTP_HOST=smtp.hostinger.com \
     SMTP_PORT=465 \
     SMTP_USER=you@yourdomain.com \
     SMTP_PASSWORD="<your-mailbox-password>" \
     FROM_EMAIL=you@yourdomain.com \
     RECIPIENT_EMAIL=you@yourdomain.com \
     python send.py
   ```
3. Click Approve in your inbox; script returns.

Hostinger-specific gotchas:

- **`from_email` must equal `SMTP_USER`** — Hostinger rejects
  sending from a different address even on the same domain
- **Use port 465 if 587 fails** (or vice versa) — some plans only
  enable one; the script auto-switches between SSL and STARTTLS
- **Outbound rate limits per mailbox per hour** — one test won't
  trigger them; a verifier-reject loop could

## What this catches that the file-transport smoke doesn't

- Real DNS resolution + TLS / STARTTLS to the provider
- Actual rendering in real mail clients (Gmail, Outlook, Apple
  Mail) — buttons survive the client's email-CSS sandbox
- The `from_email` clears SPF / DKIM / DMARC at the recipient
- The magic-link URL is reachable from a different browser (your
  phone, your laptop) than the one that ran the test
- The Python SDK's poll loop resolves on real out-of-band human
  action, not a scripted POST

## Re-runs

The identity ID is hardcoded as `email-e2e-real-py` and uses
upsert semantics — running again with different transport
credentials overwrites the config in the DB. No need to delete
anything between runs.

If you want to clean up after testing:

```sh
TOKEN=$(cat ~/.awaithumans-dev.json | jq -r .admin_token)
curl -X DELETE \
  -H "Authorization: Bearer $TOKEN" \
  http://localhost:3001/api/channels/email/identities/email-e2e-real-py
```

## Troubleshooting

| Symptom | Fix |
|---|---|
| `Couldn't find an admin token` | Start `awaithumans dev` first — the Python SDK reads its discovery file |
| `RESEND_API_KEY required` | Pass it to the command (see Option A) |
| Email never arrives | Check `awaithumans dev` logs for the email-channel error. Common causes: invalid API key, sender not verified in Resend, SMTP creds wrong, TLS mode mismatch (try `SMTP_TLS_MODE=ssl` or `starttls` to override) |
| `5xx` clicking the magic link | Token expired (24h TTL) or already consumed — magic links are single-use. Re-run the script for a fresh token |
| Email arrives but no buttons | Response schema isn't a single boolean. Multi-field forms render as a "Review in dashboard" link-out (intentional) |
