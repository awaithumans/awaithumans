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

**One primitive:** `awaitHuman()` — the agent awaits a human like it awaits a promise.

---

## Monorepo Structure

```
awaithumans/
├── packages/
│   ├── core/                     # The SDK. Exports awaitHuman(), types, schemas, test client.
│   │   └── src/                  #   This is what `npm install awaithumans` gives you.
│   │       ├── index.ts          #   Public API — named exports only.
│   │       ├── types.ts          #   All shared TypeScript types and interfaces.
│   │       ├── schemas.ts        #   Zod schema helpers and JSON Schema utilities.
│   │       ├── await-human.ts    #   The awaitHuman() function (direct mode).
│   │       ├── idempotency.ts    #   Canonical hashing + idempotency key generation.
│   │       ├── errors.ts         #   All error classes. Every error has a code + docs URL.
│   │       └── testing.ts        #   createTestClient() — in-memory server for tests.
│   │
│   ├── server/                   # The HTTP server. Hono + Drizzle + SQLite/Postgres.
│   │   └── src/                  #   Runs via `npx awaithumans dev` or Docker.
│   │       ├── index.ts          #   Server entrypoint. Hono app creation.
│   │       ├── routes/           #   One file per route group (tasks, webhooks, auth, health).
│   │       ├── db/               #   Drizzle schema, migrations, connection.
│   │       ├── services/         #   Business logic (task lifecycle, notification dispatch, verification).
│   │       └── middleware/       #   Auth, CORS, error handling, request logging.
│   │
│   ├── dashboard/                # Next.js 15 web UI. Self-hostable.
│   │   ├── app/                  #   App Router pages.
│   │   ├── components/           #   React components (shadcn/ui based).
│   │   └── lib/                  #   Client-side utilities, API client, hooks.
│   │
│   ├── cli/                      # CLI tool. `npx awaithumans dev`, `add-user`, etc.
│   │   └── src/
│   │       ├── index.ts          #   CLI entrypoint. Command registration.
│   │       └── commands/         #   One file per command (dev, add-user, version).
│   │
│   ├── adapters/
│   │   ├── temporal/             # Temporal adapter: signal-based suspend + callback handler.
│   │   │   └── src/
│   │   │       ├── index.ts      #   Exports awaitHuman() (Temporal-durable version).
│   │   │       ├── workflow.ts   #   Signal handler + sleep race logic.
│   │   │       └── callback.ts   #   createTemporalCallbackHandler() for the user's API server.
│   │   │
│   │   ├── langgraph/            # LangGraph adapter: interrupt/resume + callback handler.
│   │   │   └── src/
│   │   │       ├── index.ts
│   │   │       ├── interrupt.ts
│   │   │       └── callback.ts
│   │   │
│   │   └── verifier-claude/      # Reference AI verifier using Claude. BYO model via Verifier interface.
│   │       └── src/
│   │           ├── index.ts
│   │           └── verifier.ts   #   claudeVerifier() factory function.
│   │
│   ├── channels/
│   │   ├── slack/                # Slack channel: Block Kit rendering, interactions, NL threads.
│   │   │   └── src/
│   │   │       ├── index.ts
│   │   │       ├── renderer.ts   #   JSON Schema → Block Kit message builder.
│   │   │       ├── interactions.ts  # Slack interaction handler (button clicks, modal submits).
│   │   │       └── nl.ts         #   Natural language thread reply handler.
│   │   │
│   │   └── email/                # Email channel: Resend templates, confirmation pages, NL replies.
│   │       └── src/
│   │           ├── index.ts
│   │           ├── renderer.ts   #   JSON Schema → email HTML (React Email).
│   │           ├── confirmation.ts  # Confirmation page endpoint.
│   │           └── nl.ts         #   Email reply NL parser.
│   │
│   └── python-sdk/               # Python SDK: httpx + Pydantic. Direct mode only (adapters later).
│       ├── awaithumans/
│       │   ├── __init__.py
│       │   ├── client.py         #   await_human() async + await_human_sync()
│       │   ├── types.py          #   Pydantic models for task, response, config
│       │   └── errors.py         #   Error classes mirroring the TS SDK
│       ├── pyproject.toml
│       └── tests/
│
├── examples/
│   ├── quickstart/               # Minimal direct-mode example (TS + Python)
│   ├── temporal/                 # Real Temporal workflow with signal-based HITL
│   ├── langgraph/                # Real LangGraph agent with interrupt/resume
│   └── slack-native/             # Full Slack-native task completion
│
├── docs/                         # Nextra docs site (awaithumans.dev)
├── CLAUDE.md                     # You are here
├── CONTRIBUTING.md
├── ARCHITECTURE.md
├── README.md
├── docker-compose.yml
├── turbo.json
├── biome.json
├── tsconfig.base.json
├── pnpm-workspace.yaml
└── package.json
```

### Package Dependency Rules

These are HARD rules. Violating them is a build error.

```
core          → depends on NOTHING (zero runtime dependencies except zod)
server        → depends on core
dashboard     → depends on NOTHING from other packages (talks to server via HTTP API)
cli           → depends on core, server (embeds server for `dev` command)
adapters/*    → depends on core ONLY (never on server, dashboard, or other adapters)
channels/*    → depends on core ONLY (never on server, dashboard, or other channels)
python-sdk    → depends on NOTHING (standalone HTTP client, talks to server via API)
examples/*    → can depend on anything (they demonstrate usage)
```

**Why:** adapters and channels must be independently installable. A user who
installs `@awaithumans/temporal` should not pull in the Slack SDK, the
dashboard, or Postgres drivers. Each package has exactly the dependencies
it needs.

---

## Coding Standards

### Language and Runtime

- **TypeScript** with strict mode (`"strict": true` in tsconfig). No `any` types
  except in explicitly marked escape hatches (`// eslint-disable-next-line -- reason`).
- **Node 20+** as the minimum runtime. Use ES modules (`"type": "module"`).
- **No default exports.** Named exports only, everywhere. Default exports create
  import inconsistencies across tools.

### Style and Formatting

- **Biome** for both linting and formatting. Not ESLint. Not Prettier. One tool.
- Run `pnpm check` before every commit. CI enforces this.
- Indentation: tabs (Biome default).
- Quotes: double quotes.
- Semicolons: yes.
- Trailing commas: all.
- Line width: 100.

### File Organization

- **One file = one responsibility.** If a file has two unrelated things, split it.
- **File names are kebab-case:** `await-human.ts`, `task-store.ts`, `block-kit-renderer.ts`.
- **Directory names are kebab-case:** `packages/verifier-claude/`, `src/routes/`.
- **Index files are re-exports only.** `index.ts` should contain `export { ... } from "./file"` 
  statements and NOTHING else. No logic in index files.
- **Tests live next to the code:** `await-human.ts` → `await-human.test.ts` in the same directory.
- **Keep files under 300 lines.** If a file grows past 300 lines, it's doing too much — split it.
  This also helps AI agents reason about the code (smaller context = better edits).

### TypeScript Patterns

```ts
// DO: use interfaces for public contracts
interface Verifier {
  verify(context: VerificationContext): Promise<VerifierResult>;
  maxAttempts: number;
}

// DO: use type aliases for unions and intersections
type AssignTo = string | string[] | { pool: string } | { role: string };

// DO: use Zod schemas for runtime validation at boundaries
const TaskInput = z.object({
  task: z.string().min(1),
  timeoutMs: z.number().int().min(60_000).max(2_592_000_000),
});

// DO: named exports
export { awaitHuman } from "./await-human";

// DON'T: default exports
export default function awaitHuman() {} // NEVER

// DON'T: classes for stateless logic — use plain functions
class TaskService { ... } // AVOID unless managing state

// DO: functions that take an options object for >2 params
function awaitHuman(options: AwaitHumanOptions): Promise<T> { ... }

// DON'T: positional args for >2 params
function awaitHuman(task: string, payload: unknown, schema: ZodType, timeout: number) // NEVER
```

### Error Handling

Every error the developer can encounter must follow the **what → why → fix → docs** pattern:

```ts
// DO:
throw new AwaitHumansError({
  code: "TIMEOUT_EXCEEDED",
  message: `Task "${task}" timed out after ${timeoutMs / 1000} seconds.`,
  hint: "Check: (1) Is your notification channel configured? (2) Did the human receive the notification? (3) Consider increasing timeoutMs.",
  docsUrl: "https://awaithumans.dev/docs/troubleshooting#timeout",
});

// DON'T:
throw new Error("TIMEOUT_EXCEEDED"); // No context, no fix, no docs link
```

All error classes live in `packages/core/src/errors.ts`. Every error has:
- `code`: machine-readable string (`TIMEOUT_EXCEEDED`, `SCHEMA_VALIDATION_FAILED`, etc.)
- `message`: human-readable what-happened
- `hint`: probable cause + how to fix
- `docsUrl`: link to the relevant docs page

### Testing

- **Vitest** for all TypeScript tests. Not Jest.
- **pytest** for Python tests.
- Tests live next to the code: `foo.ts` → `foo.test.ts`.
- Use `createTestClient()` from `packages/core` for integration tests —
  it runs an in-memory server, no Docker needed.
- Every public function has at least one test.
- Every error code has a test that triggers it.
- Every example in `/examples` is tested in CI (runs end-to-end).

### Database

- **Drizzle ORM** for all database access. Not Prisma. Not raw SQL.
- Schema lives in `packages/server/src/db/schema.ts`.
- Migrations are auto-generated by Drizzle Kit.
- SQLite for dev (`npx awaithumans dev`). Postgres for production.
- Both must pass the same test suite — never write SQLite-only or Postgres-only code.

### HTTP Server

- **Hono** for all HTTP routes. Not Express. Not Fastify.
- Routes live in `packages/server/src/routes/`, one file per route group.
- Every route validates input with Zod before processing.
- Every route returns typed JSON responses.
- No middleware that silently mutates the request.

---

## The Four Adapter Buckets

The core architecture has exactly four extension points. All customization
flows through one of these. There is no fifth bucket.

| Bucket | Interface | What it does | Reference implementation |
|---|---|---|---|
| **Channel** | `Channel` | Notify humans + render task UI + accept responses | `@awaithumans/channel-slack` |
| **Verifier** | `Verifier` | Check completed work quality + parse NL responses | `@awaithumans/verifier-claude` |
| **Router** | `Router` | Resolve `assignTo` intent into concrete human assignments | Default pool router in `packages/server` |
| **Task-type handler** | `TaskTypeHandler` | Render payload + response form for a specific task type | Default JSON Schema renderer in `packages/server` |

### How to Add a New Adapter

1. Create a new directory: `packages/adapters/my-adapter/` or `packages/channels/my-channel/`
2. Add a `package.json` with `"name": "@awaithumans/my-adapter"`
3. Implement the relevant interface (see `packages/core/src/types.ts`)
4. Add tests (use `createTestClient()` for integration tests)
5. Add to `pnpm-workspace.yaml`
6. Add an entry in the root README under "Community Adapters"

An adapter depends on `packages/core` ONLY. Never import from `server`, `dashboard`,
or other adapters.

### How to Add a New Durable Adapter (e.g., a new workflow engine)

A durable adapter has two halves:

1. **SDK side** (`src/index.ts`): exports `awaitHuman()` that creates the task
   in the server and suspends the workflow using the engine's native primitive.
2. **Callback side** (`src/callback.ts`): exports `createXCallbackHandler()` that
   the user mounts in their API server — receives the webhook from the awaithumans
   server and translates it into the engine's native signal.

Both halves must handle idempotency (extract the engine's execution identity for
the idempotency key).

---

## Commit and PR Conventions

- **Conventional commits:** `feat:`, `fix:`, `docs:`, `refactor:`, `test:`, `chore:`
- **Scope by package:** `feat(core): add timeout validation`, `fix(server): handle concurrent task claims`
- **PR titles match the commit convention.**
- **One logical change per PR.** Don't mix features, refactors, and dependency updates.
- **Every PR must pass CI:** lint (Biome), test (Vitest), build, type-check.
- **Breaking changes:** prefix with `feat!:` or `fix!:`. Must be discussed in a GitHub Discussion first.

---

## What NOT to Do

- **Don't add dependencies without justification.** Every new dependency is a supply chain risk
  and a bundle size increase. If the standard library or an existing dep can do it, use that.
- **Don't use `any`.** Use `unknown` and narrow with Zod or type guards.
- **Don't write platform-specific code** (Node-only APIs) in `packages/core`. Core must work
  in Node, Bun, Deno, and edge runtimes.
- **Don't put business logic in route handlers.** Routes validate input and call services.
  Services contain logic. This keeps routes thin and testable.
- **Don't import across package boundaries** except through the published API (`index.ts`).
  Never import `../../server/src/internal-thing.ts` from an adapter.
- **Don't add a fifth adapter bucket.** If a feature doesn't fit channels, verifiers,
  routers, or task-type handlers, it's either out of scope or needs to be composed from
  existing buckets.
- **Don't fork the core for a specific customer's use case.** Per-customer divergence
  goes into adapters. This rule is non-negotiable. See `pillars/02-positioning.md` for why.
- **Don't write to the database from anywhere except `packages/server`.** Adapters and
  channels talk to the server via HTTP API. The server owns the database.
