# email-end-to-end

Real-delivery email test. Same shape as
[`../email-smoke/`](../email-smoke/) but configured for an actual
provider — you receive the email in your real inbox and click the
Approve button by hand. The TypeScript SDK long-polls until your
click lands.

This is the test that exercises the FULL pipeline:

- TS SDK creates the task
- Server resolves the email channel + identity
- Real provider (Resend / SMTP) ships the email through real DNS
- Email lands in your inbox, with HTML + text bodies, magic-link
  buttons, the works
- You click "Approve" — the action endpoint completes the task
  with the value baked into the signed token
- TS SDK's `awaitHuman` resolves with the typed response

Pick whichever transport you have credentials for.

## Option A — Resend (recommended; 5 minutes)

Fastest path. Resend's free tier is enough for this and they have a
no-setup sender (`onboarding@resend.dev`) so you can skip domain
verification.

1. Sign up at https://resend.com — free tier is generous.
2. Go to **API Keys** → **Create API Key** → name it whatever, full
   access. Copy the `re_…` value.
3. Run:
   ```sh
   cd examples/email-end-to-end
   npm install
   AWAITHUMANS_TEST_TRANSPORT=resend \
     RESEND_API_KEY=re_xxxxxxxxxxxxxxxxxxxxxxxx \
     RECIPIENT_EMAIL=you@example.com \
     npm start
   ```
4. Check your inbox — you should see a "Review: Approve this
   real-delivery test" email within 1–2 seconds. Click **Approve**.
5. The script prints `✓ Approved — task completed end-to-end via
   real email` and exits.

If you want to send from your own domain instead of
`onboarding@resend.dev`:

- In Resend, **Domains → Add Domain** → follow the DNS verification
- Then pass `FROM_EMAIL=alerts@yourdomain.com` to the npm command

## Option B — SMTP (Gmail App Password)

Use this if you're testing against your own SMTP server, AWS SES,
Mailgun, or want the Gmail-via-SMTP path.

For Gmail specifically (a common dev setup):

1. Enable 2FA on the Google account (required for App Passwords):
   https://myaccount.google.com/security
2. Generate an App Password:
   https://myaccount.google.com/apppasswords
   Pick "Mail" → "Other (custom name)" → name it `awaithumans-dev`.
   Google shows you a 16-character password. Copy it (no spaces).
3. Run:
   ```sh
   cd examples/email-end-to-end
   npm install
   AWAITHUMANS_TEST_TRANSPORT=smtp \
     SMTP_HOST=smtp.gmail.com \
     SMTP_PORT=587 \
     SMTP_USER=you@gmail.com \
     SMTP_PASSWORD="<the 16-char app password>" \
     FROM_EMAIL=you@gmail.com \
     RECIPIENT_EMAIL=you@gmail.com \
     npm start
   ```
4. Check your inbox; click Approve; script returns.

For other SMTP providers, swap `SMTP_HOST`/`SMTP_PORT`/`SMTP_USER`/
`SMTP_PASSWORD`/`FROM_EMAIL` accordingly. AWS SES needs SMTP
credentials (not your IAM key); Mailgun's SMTP creds are in their
dashboard. The same flags work everywhere.

### Option B-bis — Hostinger Mail (custom domain on Hostinger hPanel)

Hostinger uses port 465 with SSL (implicit TLS). The script
auto-detects port 465 and switches off STARTTLS — no extra flag
needed.

1. **Get your mailbox credentials.** In Hostinger hPanel → Emails
   → pick the mailbox → "Connect Apps & Devices" (or "Configure
   Desktop App"). Hostinger shows the SMTP host, port, and the
   password is whatever you set when you created the mailbox.
   Common values:
   - **SMTP host**: `smtp.hostinger.com`
   - **SMTP port**: `465` (SSL — preferred) or `587` (STARTTLS)
   - **Username**: your full email address (`you@yourdomain.com`)
   - **Password**: the mailbox password you set in hPanel
     (NOT your Hostinger account password)
2. **Run:**
   ```sh
   cd examples/email-end-to-end
   npm install
   AWAITHUMANS_TEST_TRANSPORT=smtp \
     SMTP_HOST=smtp.hostinger.com \
     SMTP_PORT=465 \
     SMTP_USER=you@yourdomain.com \
     SMTP_PASSWORD="<your-mailbox-password>" \
     FROM_EMAIL=you@yourdomain.com \
     RECIPIENT_EMAIL=you@yourdomain.com \
     npm start
   ```
3. Click Approve in your inbox; script returns.

Hostinger-specific gotchas:

- **`from_email` must be the same mailbox you authenticated as.**
  Hostinger's SMTP rejects sending from a different address even if
  the domain matches. Set `FROM_EMAIL` and `SMTP_USER` to the same
  value.
- **Use port 465 if 587 fails.** Some Hostinger plans only enable
  one — the dashboard shows you which. The script auto-flips
  between SSL and STARTTLS based on the port.
- **Check the "Sending limits" page** in hPanel before running this
  in a loop. Hostinger throttles outbound mail per mailbox per
  hour; one test send won't hit it but a verifier-rejection cycle
  could.

## What this catches that the smoke test doesn't

- Real DNS resolution + TLS / STARTTLS to the provider
- Actual rendering in real mail clients (Gmail, Outlook, Apple
  Mail) — buttons survive the client's email-CSS sandbox
- The `from_email` is well-formed enough for SPF / DKIM / DMARC
  not to bounce it
- The magic-link URL is reachable from a browser that didn't run
  the test (your phone, your laptop, etc.)

## Re-runs

The identity ID is hardcoded as `email-e2e-real` and uses upsert
semantics — running again with a different `RESEND_API_KEY` or
SMTP host just overwrites the config in the DB. No need to delete
anything between runs.

If you want to clean up after the test:

```sh
TOKEN=$(cat ~/.awaithumans-dev.json | jq -r .admin_token)
curl -X DELETE \
  -H "Authorization: Bearer $TOKEN" \
  http://localhost:3001/api/channels/email/identities/email-e2e-real
```

## Troubleshooting

| Symptom | Fix |
|---|---|
| `Couldn't find an admin token` | Start `awaithumans dev` first — the SDK reads its discovery file |
| `RESEND_API_KEY required` | Pass it as a flag (see Option A) |
| Email never arrives | Check `awaithumans dev` logs for the email-channel error. Common causes: invalid API key, sender not verified in Resend, SMTP creds wrong |
| `5xx` from clicking the magic link | Token expired (default TTL is 24h) or already consumed — magic links are single-use |
| Email arrives but no buttons, just a "Review in dashboard" link | The response schema isn't a single boolean. The renderer falls back to the dashboard link-out for multi-field forms — this is expected behavior. Click the dashboard link instead |
