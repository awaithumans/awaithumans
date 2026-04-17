# Code Quality — Agent Cleanup Rules

This file is an **invocable checklist** for AI coding agents. Contributors can point their agent at it: *"Apply CODE_QUALITY.md to packages/X"* and expect a mechanical cleanup pass.

It complements — does **not** replace — `CLAUDE.md`. CLAUDE.md describes *how the project is structured*; this file describes *what a clean diff looks like and how to verify it*.

---

## How to use

```
Apply the rules in CODE_QUALITY.md to <file-or-directory>.
Before proposing edits, run the "Commands" section and fix everything it surfaces.
Then walk the rules section and report any remaining violations.
```

---

## Commands (run these first — they catch 80%)

### Python (`packages/python/`)

```bash
cd packages/python

# Auto-fix safe modernizations + import order + unused imports
ruff check awaithumans/ --select F401,I001,UP037,UP035,UP032,SIM105,SIM210 --fix

# Full lint — must be clean before committing
ruff check awaithumans/
ruff format --check awaithumans/

# Types must be clean
mypy awaithumans/

# Tests must pass
python -m pytest tests/
```

### TypeScript / dashboard (`packages/dashboard/`, `packages/typescript-sdk/`)

```bash
cd packages/dashboard   # or packages/typescript-sdk

# Types must be clean
npx tsc --noEmit

# Biome: lint + format
npx biome check --apply .
```

**A diff is not ready until every command above returns clean.** No "I'll fix the lint in a follow-up."

---

## Rules

### 1. Directory structure

- **Folders for concepts expected to grow.** If a concept will plausibly outgrow one file (a workflow adapter, a channel renderer), start it as a folder with `__init__.py` even when today's stub is tiny. Retrofitting from file → package is pure churn.
- **Don't create `lib/api/` inside a Next.js app.** `app/api/*/route.ts` is reserved by Next.js for server routes; a sibling `lib/api/` clashes semantically. Name the client-side folder after what it *is* (`lib/server/` = "client for the Python server").
- **Never leave empty scaffolding.** An empty `packages/dashboard/packages/` left over from a misstep is noise. Delete it.

### 2. Models and schemas — where they live

Summary of `CLAUDE.md` §1, which is authoritative; linked here so the agent can verify both.

| Kind | Correct home |
|---|---|
| Pydantic request/response | `server/schemas/{domain}.py` — **never** in `routes/*.py` |
| Service exceptions | `server/services/exceptions.py` — **never** inline in service files |
| DB tables | `server/db/models/{domain}.py` |
| SDK public types | `types/{domain}.py` |
| TS API response shapes | `lib/types.ts` — **never** in API-client files |

Found a model defined inside a route file? Move it to the matching schemas file. Update `schemas/__init__.py` re-exports so import paths through the package stay stable.

### 3. Constants — no magic values

- **All numbers, strings, URLs, colors, timeouts, thresholds** → `awaithumans/utils/constants.py` (Python) or `lib/constants.ts` (dashboard).
- **Exceptions that stay inline:** a single value tightly bound to one primitive (crypto wire format bytes, regex compiled next to its only caller). When in doubt, centralize.
- **Cross-package constants must share a source.** If the Python server has `SELECT_RADIO_THRESHOLD = 4`, the dashboard's `lib/constants.ts` must define the same value at the same name. They can't drift — the dashboard mirrors a server-side UX decision.
- **Brand colors go through Tailwind `@theme`.** No `bg-[#00E676]`. Define `--color-brand` in `app/globals.css` inside `@theme { }` and use `bg-brand`, `text-brand`. Canvas/DOM APIs that can't use classes read `getComputedStyle(document.documentElement).getPropertyValue("--color-brand")` with a literal fallback.

### 4. Imports and encapsulation

- **No private cross-module imports.** `from ...mod import _private_fn` from another module means `_private_fn` isn't actually private. Rename to `public_fn` and update call sites.
- **No inline imports inside functions** unless it's a genuinely lazy optional-dependency load. If the import is used every call, move it to the top.
- **Prune unused imports.** `ruff check --select F401` finds these; run it before every commit.
- **Sort imports.** `ruff check --select I001 --fix` enforces it.

### 5. Exceptions

- **Name ends in `Error`.** `InvalidActionToken` → `InvalidActionTokenError`. Enforced by `ruff N818`.
- **Chain or suppress inside except.** Never bare `raise Other(...)` inside `except` — write `raise Other(...) from err` when the cause is useful, or `raise Other(...) from None` when the original is noise (e.g., re-raising a user-friendly "install this extra" message over an `ImportError`). Enforced by `ruff B904`.
- **No bare `except:`.** Catch specific types.
- **Routes have zero try/except.** Domain exceptions (`ServiceError` subclasses) propagate to the centralized handler in `core/exceptions.py`. Adding a new error = one class, zero handler code.
- **SDK errors follow the what → why → fix → docs pattern** (see `errors.py` for the base).

### 6. Simplifications

Ruff auto-fixes most of these:

| Smell | Fix |
|---|---|
| `try: ... except X: pass` | `from contextlib import suppress; with suppress(X): ...` |
| `True if cond else False` | `bool(cond)` or just `cond` |
| `list["ForwardRef"]` with `from __future__ import annotations` | `list[ForwardRef]` — quotes are obsolete |
| `f"some string" % args` accidentally | never use `%` with f-strings |
| `Type[Union[X, None]]` manually unwrapped | use `types.UnionType` + `typing.Union` fallback, or `Optional[X]` |

### 7. File size

- **~300 lines is the soft ceiling.** Over that, look for a structural split (by category, by concern, by surface).
- **Cohesive pairs stay together.** A Pydantic class plus its one-line DSL helper function is **one unit**, not two — leave them in the same file even if you're splitting sibling files by category. Same for a protocol plus its `SendRequest`/`SendResult` types.
- **If the split doesn't reduce coupling, don't split.** A 381-line switch-statement dispatcher is fine as-is; fragmenting it across N files means the reader chases indirection for no clarity win.

### 8. Naming

- **Snake_case Python filenames**, PascalCase classes, UPPER_CASE constants.
- **Folders never share names with framework-reserved directories.** Next.js owns `app/api/` — don't create `lib/api/`. Pick a name that describes what the module *is* (`lib/server/` not `lib/api/`).
- **Don't suffix "Service"/"Manager"/"Handler"** unless the file actually holds a service/manager/handler object. Free functions in a `*_service.py` module are fine; a `TaskServiceManagerHandler` class is not.

### 9. Comments

- **Comment the WHY, not the WHAT.** Code says what; comments explain the hidden constraint, the bug workaround, the subtle invariant.
- **No comments about the current task.** `# added for ticket #123` and `# used by the Slack flow` rot within weeks. If the reason is real, it belongs in git/PR history.
- **No multi-paragraph docstrings.** One tight sentence per function is the norm; four-paragraph preambles usually mean the function is doing too much.

### 10. Tests evolve with refactors

- When you split a package, structure-aware tests break. Example: a test that asserts `hmac` is imported in `routes/slack.py` must update to `routes/slack/oauth.py` after the package split. **Don't delete the test to silence it** — update the assertion to follow the symbol.
- Any test that patches a private function on import must update if the function becomes public.

### 11. Frontend specifics

- **Colors via `@theme` tokens** (rule 3 recap). No `[#hex]` Tailwind arbitraries in component files.
- **Canvas / DOM drawing APIs** can't use Tailwind classes — read the CSS var at runtime, fall back to a literal:
  ```ts
  ctx.strokeStyle =
    getComputedStyle(document.documentElement)
      .getPropertyValue("--color-fg")
      .trim() || "#f5f5f5";
  ```
- **Types in `lib/types.ts`, never in API-client files.** Re-export from `lib/server/index.ts` for import-site convenience.
- **Centralize polling intervals, truncation lengths, UX thresholds** in `lib/constants.ts`.

### 12. Ruff config stays honest

If a rule fires on idiomatic framework code (FastAPI's `Depends` in defaults trips `B008`), **configure the exception in `pyproject.toml`** — don't silence per-line with `# noqa`. The config lives at the project level, not the file level.

The current allowlist lives under `[tool.ruff.lint.flake8-bugbear]` → `extend-immutable-calls`.

---

## What this file is NOT

- Not a style guide (that's `CLAUDE.md`'s "Coding Standards" section).
- Not aspirational — every rule here came from a real smell fixed in this repo. If you're adding one, link the PR.
- Not for feature work. Use it for **cleanup sweeps** and **pre-commit review**, not for "go build X."

---

## Example invocation

```
Apply CODE_QUALITY.md to packages/python/awaithumans/server/channels/.
Run the Commands section first, fix what it finds, then walk Rules 1–12.
Report violations as a list; don't edit without showing me the plan.
```
