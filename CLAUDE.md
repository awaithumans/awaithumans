# awaithumans — Codebase Guide

This file is the source of truth for how code is written in this repo. It is
read by human developers, AI coding agents (Claude Code, Copilot, Cursor),
and CI. Follow it exactly.

---

## What This Project Is

An open source infrastructure package that lets AI agent workflows delegate
tasks to human beings — with task routing, notifications (Slack, email),
a review dashboard, AI verification of completed work, and a callback system
to resume the agent when the human is done.

**One primitive:** `await_human()` / `awaitHuman()` — the agent awaits a human
like it awaits a promise.

---

## Architecture Overview

The project has three packages:

1. **Python package** (`packages/python/`) — the API server, CLI, channels,
   verification, AND the Python SDK. Published as `awaithumans` on PyPI.
   This is the brain of the system.

2. **Dashboard** (`packages/dashboard/`) — Next.js 16 web UI. Pre-built to
   static files and bundled into the Python package for production. Separate
   dev server for development.

3. **TypeScript SDK** (`packages/typescript-sdk/`) — the npm `awaithumans`
   package. A thin HTTP client to the Python API server. Includes adapter
   subpath exports for Temporal and LangGraph.

```
Developer's agent code                  The awaithumans system
─────────────────────                   ──────────────────────

  Python agent                           ┌─────────────────────────┐
  ┌──────────────┐      HTTP             │  API Server (Python)    │
  │ from         │ ──────────────────►   │  FastAPI + SQLModel     │
  │ awaithumans  │                       │                         │
  │ import       │                       │  Owns:                  │
  │ await_human  │                       │  - Task store (DB)      │
  └──────────────┘                       │  - Slack channel        │
                                         │  - Email channel        │
  TypeScript agent                       │  - AI verification      │
  ┌──────────────┐      HTTP             │  - Webhook dispatch     │
  │ import {     │ ──────────────────►   │  - Long-poll endpoint   │
  │  awaitHuman  │                       │  - Audit trail          │
  │ } from       │                       └────────────┬────────────┘
  │ "awaithumans"│                                    │
  └──────────────┘                                    │ serves static files
                                         ┌────────────▼────────────┐
                                         │  Dashboard (Next.js)    │
                                         │  Pre-built static files │
                                         │  Task queue, audit log  │
                                         └─────────────────────────┘
```

---

## Monorepo Structure

```
awaithumans/
├── packages/
│   ├── python/                       # PyPI: awaithumans (SDK + server + CLI)
│   │   ├── awaithumans/
│   │   │   ├── __init__.py           # SDK public API: await_human, types, errors
│   │   │   ├── client.py             # await_human() async + await_human_sync()
│   │   │   ├── types.py              # Pydantic models: AwaitHumanOptions, TaskRecord, etc.
│   │   │   ├── errors.py             # Error classes (what → why → fix → docs pattern)
│   │   │   ├── temporal.py           # Temporal adapter (pip install "awaithumans[temporal]")
│   │   │   ├── langgraph.py          # LangGraph adapter (pip install "awaithumans[langgraph]")
│   │   │   ├── verifier_claude.py    # Claude verifier config helper
│   │   │   │
│   │   │   ├── server/               # FastAPI server (pip install "awaithumans[server]")
│   │   │   │   ├── __init__.py
│   │   │   │   ├── app.py            # FastAPI app factory + dashboard static mount
│   │   │   │   ├── routes/           # One file per route group (tasks, webhooks, auth, health)
│   │   │   │   ├── db/               # SQLModel schema, Alembic migrations, connection
│   │   │   │   ├── services/         # Business logic (task lifecycle, notifications, verification)
│   │   │   │   ├── channels/         # Slack (slack-sdk) + Email (resend) — server-side
│   │   │   │   └── verification/     # AI verifier execution (anthropic SDK, etc.)
│   │   │   │
│   │   │   └── cli/                  # CLI commands
│   │   │       └── main.py           # `awaithumans dev`, `awaithumans add-user`, `awaithumans version`
│   │   │
│   │   ├── pyproject.toml            # One package, multiple extras: [server], [temporal], [langgraph]
│   │   └── tests/
│   │
│   ├── dashboard/                    # Next.js 16 web UI (standalone React app)
│   │   ├── app/                      # App Router pages
│   │   ├── components/               # shadcn/ui components (brand palette: #0A0A0A / #F5F5F5 / #00E676)
│   │   ├── lib/                      # API client, hooks, utilities
│   │   ├── generated/                # TypeScript types auto-generated from OpenAPI spec
│   │   └── package.json
│   │
│   └── typescript-sdk/               # npm: awaithumans (TS SDK — HTTP client only)
│       └── src/
│           ├── index.ts              # Public API: awaitHuman, types, errors (re-exports only)
│           ├── types.ts              # All TypeScript interfaces
│           ├── await-human.ts        # awaitHuman() — HTTP client to the Python API server
│           ├── idempotency.ts        # Canonical hashing (Web Crypto API, cross-platform)
│           ├── errors.ts             # Error classes mirroring the Python SDK
│           ├── schemas.ts            # Zod schema helpers
│           ├── reserved.ts           # awaitAgent() + awaitAny() Phase 4 stubs
│           ├── testing.ts            # createTestClient() — in-memory mock
│           └── adapters/
│               ├── temporal/         # awaithumans/temporal (subpath export)
│               │   └── index.ts      # Signal-based suspend + createTemporalCallbackHandler()
│               └── langgraph/        # awaithumans/langgraph (subpath export)
│                   └── index.ts      # Interrupt/resume + createLangGraphCallbackHandler()
│
├── examples/
│   ├── quickstart/                   # Minimal direct-mode example (Python + TS)
│   ├── temporal/                     # Real Temporal workflow with signal-based HITL
│   ├── langgraph/                    # Real LangGraph agent with interrupt/resume
│   └── slack-native/                 # Full Slack-native task completion
│
├── docs/                             # Nextra docs site (awaithumans.dev)
├── docker-compose.yml                # Production: API server + dashboard + Postgres
├── CLAUDE.md                         # You are here
├── CONTRIBUTING.md
└── README.md
```

---

## Package Dependency Rules

These are HARD rules. Violating them is a build error.

```
python SDK (awaithumans)        → depends on httpx, pydantic ONLY
python server (awaithumans[server]) → depends on fastapi, sqlmodel, slack-sdk, resend, etc.
python adapters ([temporal], [langgraph]) → depends on their engine SDKs
dashboard                       → depends on NOTHING from Python (talks to server via HTTP API)
typescript-sdk                  → depends on zod ONLY (HTTP client to server)
typescript-sdk adapters         → peerDependencies on engine SDKs (optional)
examples                        → can depend on anything
```

**Why:** the Python SDK must be lightweight (`pip install awaithumans` = just httpx + pydantic).
Server deps only install with `pip install "awaithumans[server]"`. Dashboard never imports
Python. TypeScript SDK never imports Python. Everything talks via HTTP API.

---

## Python Coding Standards

The API server and Python SDK follow these rules:

### Style and Formatting

- **Ruff** for linting and formatting. Not flake8. Not black. One tool.
- Run `ruff check . && ruff format .` before every commit.
- Line length: 100.
- Target: Python 3.9+.
- Use `from __future__ import annotations` in every file.

### Type Safety

- **Strict mypy** (`strict = true` in pyproject.toml).
- All function signatures must have type annotations.
- Use `Pydantic BaseModel` for all data structures that cross boundaries.
- Use `TypeVar` for generic functions.

### File Organization

- **One file = one responsibility.** If a file has two unrelated things, split it.
- **File names are snake_case:** `task_lifecycle.py`, `slack_channel.py`.
- **Tests live in `tests/` directory**, mirroring the source structure.
- **Keep files under 300 lines.** Split if larger.

### Patterns

```python
# DO: Pydantic models for all data structures
class TaskRecord(BaseModel):
    id: str
    status: TaskStatus
    payload: dict[str, Any]

# DO: async functions for I/O
async def create_task(options: AwaitHumanOptions) -> TaskRecord: ...

# DO: sync wrappers when needed
def create_task_sync(options: AwaitHumanOptions) -> TaskRecord:
    return asyncio.run(create_task(options))

# DO: explicit error types
raise TimeoutError(task="Approve KYC", timeout_seconds=900)

# DON'T: bare except
except Exception: ...  # NEVER — catch specific exceptions

# DON'T: mutable default arguments
def func(items: list[str] = []) -> None: ...  # NEVER — use Field(default_factory=list)
```

### Error Handling

Every error follows the **what → why → fix → docs** pattern (see `errors.py`).

### Database

- **SQLModel** for all database access (SQLAlchemy + Pydantic hybrid).
- **Alembic** for migrations.
- SQLite for dev (`awaithumans dev`). Postgres for production.
- Both must pass the same test suite.

### HTTP Server

- **FastAPI** for all API routes.
- Routes in `server/routes/`, one file per route group.
- Every route validates input with Pydantic models.
- Every route returns typed Pydantic response models.
- Use dependency injection for DB sessions, auth, etc.

---

## TypeScript Coding Standards

The TypeScript SDK and dashboard follow these rules:

### Style

- **Biome** for linting and formatting. Tabs, double quotes, semicolons.
- **Strict TypeScript** (`"strict": true`).
- **No default exports.** Named exports only.
- **No `any`.** Use `unknown` and narrow with Zod or type guards.

### TypeScript SDK Specifics

- The SDK is a thin HTTP client. It calls the Python API server via HTTP.
- All validation happens server-side. The SDK validates schemas locally for
  fast feedback, then sends to the server.
- The SDK must work in Node, Bun, Deno, and edge runtimes — no `node:*` imports.
- Adapters (awaithumans/temporal, awaithumans/langgraph) are subpath exports
  with optional peer dependencies.

### Dashboard Specifics

- Next.js 16 App Router + React 19 + Tailwind + shadcn/ui.
- Brand palette: background `#0A0A0A`, foreground `#F5F5F5`, accent `#00E676`.
- TypeScript types are auto-generated from the Python API's OpenAPI spec.
- The dashboard talks to the server via HTTP API ONLY — never imports Python.
- For production: built to static files and bundled into the Python package.

---

## The Four Adapter Buckets

The core architecture has exactly four extension points. All customization
flows through one of these. There is no fifth bucket.

| Bucket | Where it runs | Python | TypeScript |
|---|---|---|---|
| **Channel** (Slack, email) | Server-side | `server/channels/` | N/A — server handles it |
| **Verifier** (AI quality check + NL parse) | Server-side | `server/verification/` | N/A — server handles it |
| **Router** (resolve assignTo → humans) | Server-side | `server/services/` | N/A — server handles it |
| **Task-type handler** (render UI from schema) | Dashboard + server | Dashboard components + API | React components |

Channels and verifiers are SERVER-SIDE (Python). The SDK (both TS and Python)
just passes configuration; the server does the actual Slack messaging, email
sending, and AI verification.

---

## Developer Experience: How Users Install

```bash
# Python developer (primary ICP):
pip install awaithumans                    # just the SDK
pip install "awaithumans[server]"          # SDK + server + CLI + bundled dashboard
awaithumans dev                            # one command, everything starts

# TypeScript developer:
npm install awaithumans                    # the TS SDK
docker compose up                          # runs the Python server + dashboard

# Anyone with Docker:
docker compose up                          # works everywhere
```

---

## Commit Conventions

- **Conventional commits:** `feat:`, `fix:`, `docs:`, `refactor:`, `test:`, `chore:`
- **Scope by package:** `feat(server): add task CRUD routes`, `fix(sdk): handle timeout edge case`
- **One logical change per PR.**

---

## What NOT to Do

- **Don't add a fifth adapter bucket.** Channels, verifiers, routers, task-type handlers. That's it.
- **Don't fork the core for a specific customer.** Per-customer divergence goes into adapters.
- **Don't put business logic in route handlers.** Routes validate input and call services.
- **Don't import Python from TypeScript or vice versa.** Everything talks via HTTP API.
- **Don't use `node:*` imports in the TypeScript SDK.** Must work on all runtimes.
- **Don't write SQLite-only or Postgres-only database code.** Both must pass the same tests.
- **Don't add server dependencies to `pip install awaithumans`.** Server deps live behind `[server]` extra.
