# awaithumans v0.1.0 — public preview

The first tagged release of `awaithumans` — the human layer for AI agents. One function call (`await_human()` / `awaitHuman()`) parks your agent until a human reviews via Slack, email, or a built-in dashboard, then resumes with a typed response.

## Highlights

- 🧠 **One primitive** in [Python](https://awaithumans.dev/docs/sdk/python) and [TypeScript](https://awaithumans.dev/docs/sdk/typescript): `await_human()` / `awaitHuman()`.
- 📬 **Three channels:** [Slack](https://awaithumans.dev/docs/channels/slack) (broadcast + DM + NL replies), [email](https://awaithumans.dev/docs/channels/email) (Resend + SMTP), built-in [dashboard](https://awaithumans.dev/docs/channels/overview#dashboard).
- 🔁 **Durable adapters:** [Temporal](https://awaithumans.dev/docs/adapters/temporal) (signal-based) and [LangGraph](https://awaithumans.dev/docs/adapters/langgraph) (interrupt/resume).
- 🤖 **AI verification** server-side: Claude / OpenAI / Gemini / Azure OpenAI ([docs](https://awaithumans.dev/docs/adapters/verifier)).
- 🪪 **User directory + routing** by email, list, pool, or role with least-recently-assigned fairness.
- 🛡️ **Self-host in one command:** `awaithumans dev` for development, `docker compose up` for production.
- 📦 **Apache 2.0** across the whole stack — SDK, server, dashboard, adapters, channels. Free forever for self-hosted use, with an explicit patent grant.

## Install

```bash
# Python
pip install "awaithumans[server]"
awaithumans dev

# TypeScript
npm install awaithumans
```

Then [walk the quickstart](https://awaithumans.dev/docs/quickstart) — first task in five minutes.

## What's in this release

### SDK & core

- `await_human()` / `await_human_sync()` — the core primitive (Python)
- `awaitHuman()` — the equivalent in TypeScript
- Pydantic schema validation (Python), Zod schema validation (TypeScript)
- Cross-platform idempotency-key generation (Node, Bun, Deno, edge runtimes)
- Error classes follow the **what → why → fix → docs** pattern in both SDKs — every error message includes a link to a docs page that explains the fix
- Strict Stripe-style idempotency: same key, same task, always — direct-mode `await_human()` is now resumable across agent restarts ([details](https://awaithumans.dev/docs/concepts/idempotency))

### Server

- FastAPI app with SQLModel + Alembic migrations, runs on SQLite (dev) or Postgres (prod)
- Task CRUD + a state machine covering 10 statuses ([lifecycle](https://awaithumans.dev/docs/concepts/task-lifecycle))
- Long-poll endpoint for direct-mode SDK clients
- Timeout scheduler using an indexed `timeout_at` column
- HMAC-signed completion webhooks with at-least-once retry over 3 days ([webhooks](https://awaithumans.dev/docs/webhooks))
- Audit trail for every state transition

### Channels

- **Slack:** DM + channel broadcast with first-to-claim semantics, Block Kit modal, OAuth install for multi-workspace, NL thread-reply parsing via the verifier, signed dashboard handoff for Slack-only users
- **Email:** Resend + SMTP transports, action buttons for boolean / single-select responses, magic-link confirmation pages, file transport for automated tests

### AI verification

- One LLM call does both quality-check and NL-parsing
- Built-in providers: Claude (Anthropic), OpenAI, Gemini (Google), Azure OpenAI
- Configurable `max_attempts`; rejection is non-terminal so the human can retry
- Skip the verifier with `redact_payload=True` for sensitive payloads

### Adapters

- **Temporal** (`pip install "awaithumans[temporal]"`, `import { awaitHuman } from "awaithumans/temporal"`) — signal-based, workflow parks for hours/days
- **LangGraph** (`pip install "awaithumans[langgraph]"`, `awaithumans/langgraph`) — interrupt/resume in a single process

### Dashboard

- Next.js 16 + React 19, statically built, bundled into the Python wheel
- Task queue, task detail, audit log, stats, settings pages
- User directory with Slack member picker
- First-run `/setup` wizard

### CLI & DX

- `awaithumans dev` — one-command server + dashboard, auto-generates `PAYLOAD_KEY` for local dev
- `npx awaithumans dev` for TypeScript developers (under the hood: `uv` runs the Python server, no Python knowledge required)
- Docker image at `ghcr.io/awaithumans/awaithumans` (linux/amd64 + linux/arm64)
- Reference `docker-compose.yml` ships with the repo
- 14 runnable examples across Python and TypeScript: quickstart, Slack, email (smoke + end-to-end), Temporal, LangGraph, verifier

### Auth & security

- argon2id password hashing for operator login
- HMAC-signed session cookies (httponly, SameSite=Lax)
- First-run bootstrap token, one-shot, printed to server log
- Admin bearer token as the automation escape hatch
- Login rate limiting per-IP and per-email
- Last-active-operator guard
- Credential scrubber on the root logger

## Known gaps

These are documented and on the post-launch roadmap:

- No session invalidation on password change (outstanding sessions survive to expiry — `session_version` field planned)
- Production `PUBLIC_URL` must be HTTPS — currently a logged error, not a boot failure
- Multi-replica deployments need a shared rate-limiter store (Redis) — planned post-launch
- In-memory `createTestClient()` is stubbed but not yet implemented — see the [Testing docs](https://awaithumans.dev/docs/testing) for the patterns that work today
- Workforce marketplace (`assign_to={"marketplace": True}`) raises `MarketplaceNotAvailableError` — reserved for [Phase 3](https://awaithumans.dev/docs/community/roadmap#marketplace)

## Migration from pre-release

If you were running off `main` before tagging:

- The strict-Stripe idempotency change is the single behavioral break. Pre-tag, a terminal task's key was released, allowing a fresh task with the same key. Now the same key always returns the same task.
- To request a fresh task for the same logical event (e.g. yesterday's task timed out, you want a new review today), pass a distinct key — convention is to suffix with `:retry-N`.
- See [Idempotency → Re-triggering a review](https://awaithumans.dev/docs/concepts/idempotency#re-triggering-a-review).

## Links

- 📚 [Documentation](https://awaithumans.dev/docs)
- 🚀 [Quickstart](https://awaithumans.dev/docs/quickstart)
- 🐛 [Report an issue](https://github.com/awaithumans/awaithumans/issues)
- 💬 [Discord](https://discord.gg/awaithumans)
- 🔒 Security disclosures: **security@awaithumans.com**

## Thanks

To everyone in the early Discord, the design partners walking through end-to-end loops on their own infrastructure, and the contributors testing edge cases nobody had hit yet — this release is for you.
