# Changelog

All notable changes to `awaithumans` are documented here.

Format based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
This project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

Dates are ISO-8601. Unreleased changes land in the top section and roll
into a versioned release when tagged.

---

## [Unreleased]

_Nothing yet — open the next change here._

---

## [0.1.1] — 2026-05-11

### Fixed

- **TypeScript SDK: widen `@langchain/langgraph` peer-dep range** to
  `"^0.2.0 || ^1.0.0"` (was `"^0.2.0"`). Users on a fresh
  `npm install awaithumans @langchain/langgraph` would get the
  current upstream (`1.x`) and hit `ERESOLVE` against the old
  pinned range. Verified the `interrupt(...)` API surface the
  adapter uses is signature-identical across both majors. No
  runtime code changed; this is purely a peer-range fix.

---

## [0.1.0] — 2026-05-11

First tagged release. Everything below is in the shipped package.

### Changed (BREAKING)

- **Idempotency keys follow strict Stripe semantics.** A task's
  `idempotency_key` always returns the same task, regardless of
  status. Previously a terminal task's key was released, allowing a
  fresh task with the same key — convenient for "re-trigger a
  review" but silently lost the human's response when an agent
  restart raced with task completion in direct mode. To request a
  fresh task for the same logical event, pass a distinct key (e.g.
  suffix with `:retry-1`). Direct-mode `await_human()` is now
  resumable across agent restarts: a re-invocation with the same
  key returns the stored response (for `COMPLETED` tasks) or the
  typed terminal error (for `TIMED_OUT` / `CANCELLED` /
  `VERIFICATION_EXHAUSTED`). Aligns the implementation with the
  Stripe model the docs already claimed.

- **Repo and packages are now Apache 2.0** across the whole stack
  (SDK, server, dashboard, adapters, channels). Pre-tag the README
  claimed a dual-license (MIT SDK + ELv2 server) that was never
  realized in pyproject.toml or package.json. The explicit patent
  grant in Apache 2.0 matters more for AI infra than the brevity of
  MIT.

### Added

**SDK & core**

- `await_human()` / `await_human_sync()` — the core primitive
- Python SDK with Pydantic schema validation
- TypeScript SDK (`awaithumans` on npm) with Zod schema validation
- Cross-platform idempotency key generation (works in Node, Bun, Deno, edge runtimes)
- Error classes with `what → why → fix → docs` shape in both SDKs
- In-memory test client (`awaithumans.testing`) for agent tests without a server

**Server**

- FastAPI app with SQLModel + Alembic migrations
- Task CRUD + state machine (created / notified / assigned /
  in_progress / submitted / completed / cancelled / timed_out)
- Long-poll endpoint for direct mode
- Timeout scheduler using indexed `timeout_at` column
- HMAC-signed webhook dispatch for completion callbacks
- Audit trail for every state transition and claim

**User directory**

- `User` model with synthetic ID primary key + nullable email / slack
  identifiers (at least one required)
- Admin API (`/api/admin/users` CRUD + password set/clear)
- CLI: `add-user`, `list-users`, `remove-user`, `set-password`,
  `bootstrap-operator`
- Task router (Option C — least-recently-assigned, transactional)
- Free-form `role` / `access_level` / `pool` labels for routing

**Auth**

- DB-backed per-user login with argon2id password hashing
- HMAC-signed session cookies (httponly, SameSite=Lax)
- First-run `/setup` bootstrap token flow (token printed to server
  log on startup when the users table is empty; one-shot)
- Admin bearer token as automation escape hatch
- Last-active-operator guard on delete / demote / deactivate
- Login timing equalization against unknown-user enumeration

**Dashboard**

- Next.js 16 + React 19 static export, bundled into the Python wheel
- Task queue, task detail, audit log, stats, settings pages
- User directory management UI with Slack workspace member picker
- First-run `/setup` wizard
- Brand palette: `#0A0A0A` / `#F5F5F5` / `#00E676`

**Channels**

- Slack: DM + channel broadcast with first-to-claim semantics,
  Block Kit form rendering, modal submission handling, OAuth install
  flow for multi-workspace, HMAC signature verification
- Email: Resend + SMTP transports, action buttons, confirmation
  pages, magic-link tokens signed with HKDF-derived key

**CLI & developer experience**

- `awaithumans dev` — one-command server + dashboard, auto-generates
  `PAYLOAD_KEY` for local dev
- `npx awaithumans dev` via `uv` — TypeScript developers never touch
  Python
- Docker image published to `ghcr.io/awaithumans/awaithumans` (multi-arch:
  linux/amd64, linux/arm64)
- `docker-compose.yml` with optional Postgres block
- Python quickstart example (`examples/quickstart/`)
- TypeScript quickstart example (`examples/quickstart-ts/`)

**Operational**

- Alembic migrations with date-based filenames (`YYYYMMDD_HHMM_slug.py`)
- GitHub Actions CI enforcing single-head alembic invariant
- Multi-arch Docker publish on tag + main push
- 306 automated tests across services, routes, and auth

### Known gaps — landing post-launch

- No rate limiting on login (argon2's CPU cost slows brute-force but
  doesn't stop it; proper limiter with Redis planned)
- No session invalidation on password change (outstanding sessions
  survive to expiry; `session_version` field planned)
- Production `PUBLIC_URL` must be HTTPS — currently a logged error,
  not a boot failure
- Temporal and LangGraph adapters are planned but not yet shipped
- AI verifier (Claude) adapter is planned but not yet shipped
