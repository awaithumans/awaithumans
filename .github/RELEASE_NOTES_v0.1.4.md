# awaithumans v0.1.4 — eight bug-fix / DX PRs + a full marketing refresh

Three days after [v0.1.3](https://github.com/awaithumans/awaithumans/releases/tag/v0.1.3). Eight server / dashboard PRs from beta-tester feedback, plus the full GitHub / PyPI / npm README refresh. No API-breaking changes; safe drop-in upgrade.

## Highlights

- 🔔 **`notification_failed` audit + banner** — when an email or Slack send can't deliver, the task page now shows an amber banner with the failure reason and the inline audit timeline gets a matching row. Email surfaces 4 failure modes; Slack surfaces 3. Operators no longer have to grep the server log to find out why a human never got pinged. ([#111](https://github.com/awaithumans/awaithumans/pull/111))
- 🌍 **East-of-UTC handoff URLs work again** — SQLite stores `task.timeout_at` tz-naive, and the email notifier was calling `.timestamp()` on it which treats the value as local time. UTC+1 users were getting links that expired 3,000 seconds before they were issued. Fix extracted to a shared `to_utc_unix` helper used by both email + Slack handoffs. ([#113](https://github.com/awaithumans/awaithumans/pull/113))
- 🔁 **No more duplicate notification emails on retries.** The create-task route was firing notify tasks unconditionally; a retry with the same idempotency key re-emailed the reviewer for an already-running task. Now gated on `was_newly_created`. ([#114](https://github.com/awaithumans/awaithumans/pull/114))
- 🪪 **`GET /api/version`** — new public endpoint for ops monitoring + pre-auth SDK compatibility probes. Returns `{"name":"awaithumans","version":"0.1.4"}`. ([#117](https://github.com/awaithumans/awaithumans/pull/117))
- 🏷 **`Idempotent-Replayed: true` header** on `POST /api/tasks` when an existing task is returned via idempotency key. Stripe-style — status stays `201`, the header is the signal. Documented in `docs/api/overview.mdx`. ([#118](https://github.com/awaithumans/awaithumans/pull/118))
- 📍 **OpenAPI docs moved to `/api/docs`** to match the docs page contract — the FastAPI defaults at root `/docs` were a framework leak. Auth-bypass updated; FastAPI's `info.version` field now reads from `awaithumans.__version__`. ([#115](https://github.com/awaithumans/awaithumans/pull/115))
- 🎨 **Brand-styled HTML error page** on email/Slack handoff link failure. Recipients clicking stale links no longer see raw FastAPI JSON in their browser. ([#116](https://github.com/awaithumans/awaithumans/pull/116))
- ⚠️ **Boot-time channel-config validator** — `EMAIL_TRANSPORT=smtp` set without `SMTP_HOST`? Warning fires at server start naming the missing env var. Same for resend / Slack OAuth / single-workspace Slack. ([#112](https://github.com/awaithumans/awaithumans/pull/112))
- 🤝 **Python and TypeScript stay mono-versioned at `0.1.4`** — TS SDK source unchanged this release (all new behaviour rides the existing wire protocol), but the version number tracks Python.

Plus a full GitHub / PyPI / npm README refresh: hero block with brand logo, "Why awaithumans" comparison table (capturing "humanlayer alternative" search traffic), copy-pasteable Quick start, "What you can build with it" use-case list, prominent adoption badges, 10 new GitHub repo topics, keyword expansion across PyPI + npm. ([#119](https://github.com/awaithumans/awaithumans/pull/119), [#120](https://github.com/awaithumans/awaithumans/pull/120), [#121](https://github.com/awaithumans/awaithumans/pull/121), [#122](https://github.com/awaithumans/awaithumans/pull/122))

## Upgrade

### Python

```bash
pip install --upgrade "awaithumans[server]==0.1.4"
# or whichever extras you use:
#   pip install --upgrade "awaithumans[temporal]==0.1.4"
#   pip install --upgrade "awaithumans[langgraph]==0.1.4"
#   pip install --upgrade "awaithumans[verifier-claude]==0.1.4"
```

### TypeScript

```bash
npm install awaithumans@0.1.4
# Or with peers if you're using the adapters:
#   npm install awaithumans@0.1.4 @temporalio/workflow @temporalio/client
#   npm install awaithumans@0.1.4 @langchain/langgraph
```

### Docker

```bash
docker pull ghcr.io/awaithumans/awaithumans:0.1.4
docker pull ghcr.io/awaithumans/awaithumans:latest
```

## What didn't change

- **No API changes** — every function in v0.1.3 still works identically in v0.1.4.
- **No breaking changes** — `pip install --upgrade` and `npm install awaithumans@latest` are safe drop-ins.
- **TypeScript SDK source unchanged** — version bump is mono-version sync only. All new server behaviour (Idempotent-Replayed header, /api/version, /api/docs path, friendly error pages) is observable from TS without any client-side changes.

## Verify the upgrade landed

```bash
python -c "import awaithumans; print(awaithumans.__version__)"
# → 0.1.4

awaithumans dev
# Boot logs should now include a "channel-config" WARNING line if any
# email/slack channel is half-configured, instead of silently failing
# at first send.

# Hit the new version endpoint:
curl http://localhost:3001/api/version
# → {"name":"awaithumans","version":"0.1.4"}
```

```bash
node -e "console.log(require('awaithumans/package.json').version)"
# → 0.1.4
```

## Links

- 📚 [Documentation](https://docs.awaithumans.dev)
- 🆕 [What's new](https://docs.awaithumans.dev/changelog)
- 🔒 Security disclosures: **security@awaithumans.dev**
- 💬 [Discord](https://discord.gg/Kewdh7vjdc) · [GitHub Discussions](https://github.com/awaithumans/awaithumans/discussions)
- 🐛 [v0.1.3 → v0.1.4 full diff](https://github.com/awaithumans/awaithumans/compare/v0.1.3...v0.1.4)
