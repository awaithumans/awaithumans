# Dashboard Embedding Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship the dashboard-embedding feature defined in `docs/superpowers/specs/2026-05-06-dashboard-embedding-design.md` — let partners drop a signed-iframe of one task review form into their own product.

**Architecture:** Headless `/embed/[taskId]` route in the dashboard, served behind a strict CSP, talks to existing API routes using a short-lived HS256 JWT (token in URL fragment). New `EmbedAuthMiddleware` recognises the bearer token; new `POST /api/embed/tokens` mints them; partner backends authenticate the mint call with a `service_api_keys` row. No new user accounts; embed end-users are identified only by the JWT's `sub` claim.

**Tech Stack:** FastAPI + SQLModel + Alembic + pyjwt (server), Next.js App Router + React 19 + Tailwind v4 (dashboard), Typer (CLI), pytest + pytest-asyncio (tests), Biome (TS formatting), Ruff (Python formatting).

**Branch:** `feat/embed-dashboard` in `/Users/ta/hitl-project/awaithumans-embed/` (worktree).

**Source of truth:** the spec at `docs/superpowers/specs/2026-05-06-dashboard-embedding-design.md` is authoritative for any rationale not repeated here.

---

## File map

### Server (Python)

- Modify: `packages/python/awaithumans/utils/constants.py` — add embed/service-key constants
- Modify: `packages/python/awaithumans/server/core/config.py` — add 3 env-var fields
- Modify: `packages/python/awaithumans/server/services/exceptions.py` — add 3 ServiceError subclasses
- Create: `packages/python/awaithumans/server/services/embed_token_service.py` — sign/verify + origin matching
- Create: `packages/python/awaithumans/server/db/models/service_api_key.py` — SQLModel
- Modify: `packages/python/awaithumans/server/db/models/__init__.py` — re-export
- Create: `packages/python/awaithumans/server/services/service_key_service.py` — CRUD
- Create: `packages/python/alembic/versions/<ts>_create_service_api_keys.py`
- Create: `packages/python/alembic/versions/<ts>_add_audit_via_columns.py`
- Modify: `packages/python/awaithumans/server/db/models/audit_log.py` — 3 new columns
- Create: `packages/python/awaithumans/server/core/embed_auth.py` — middleware
- Modify: `packages/python/awaithumans/server/core/auth.py` — skip /embed/*
- Modify: `packages/python/awaithumans/server/app.py` — wire middleware + headers
- Create: `packages/python/awaithumans/server/schemas/embed.py` — request/response models
- Create: `packages/python/awaithumans/server/routes/embed.py` — POST /api/embed/tokens
- Modify: `packages/python/awaithumans/server/routes/tasks.py` — accept embed auth on get/respond
- Modify: `packages/python/awaithumans/server/services/task_service.py` — audit fields
- Create: `packages/python/awaithumans/cli/commands/{create,list,revoke}_service_key{,s}.py`
- Modify: `packages/python/awaithumans/cli/main.py` — register CLI commands

### Dashboard (Next.js)

- Create: `packages/dashboard/app/embed/layout.tsx`
- Create: `packages/dashboard/app/embed/[taskId]/page.tsx`
- Create: `packages/dashboard/lib/embed/{token,post-message,api}.ts`

### SDKs

- Create: `packages/python/awaithumans/embed.py`
- Modify: `packages/python/awaithumans/__init__.py` — re-export
- Create: `packages/typescript-sdk/src/embed.ts`
- Create: `packages/typescript-sdk/src/types/embed.ts`
- Modify: `packages/typescript-sdk/src/{index,types/index}.ts` — re-export

### Examples + docs

- Create: `examples/embed/{server.py,index.html,README.md}`
- Create: `docs/embedding.md`

### Tests (mirroring source)

- Create: `packages/python/tests/embed/{conftest,test_constants,test_config,test_exceptions,test_token_service,test_origin_matching,test_service_key_model,test_service_key_service,test_cli_service_keys,test_embed_auth_middleware,test_mint_endpoint,test_route_authorization,test_response_headers,test_sdk_helper}.py`

---

## Phase 1 — Foundation

### Task 1: Add embed constants

**Files:**
- Modify: `packages/python/awaithumans/utils/constants.py`
- Test: `packages/python/tests/embed/test_constants.py`

- [ ] **Step 1: Failing test**

Create `packages/python/tests/embed/test_constants.py` asserting these names exist on `awaithumans.utils.constants`: `EMBED_TOKEN_DEFAULT_TTL_SECONDS == 300`, `EMBED_TOKEN_MAX_TTL_SECONDS == 3600`, `EMBED_TOKEN_MIN_TTL_SECONDS == 60`, `EMBED_TOKEN_AUDIENCE == "embed"`, `EMBED_TOKEN_ISSUER == "awaithumans"`, `EMBED_TOKEN_LEEWAY_SECONDS == 60`, `SERVICE_KEY_PREFIX == "ah_sk_"`, `SERVICE_KEY_RAW_BYTES == 20`, `SERVICE_KEY_DISPLAY_PREFIX_LENGTH == 12`, `SERVICE_KEY_MAX_NAME_LENGTH == 80`.

- [ ] **Step 2: Run** — `pytest tests/embed/test_constants.py -v` — expect AttributeError fails.

- [ ] **Step 3: Append constants to `utils/constants.py`** with a section comment `# Dashboard embedding`. Group: TTL trio, audience, issuer, leeway, then service-key family.

- [ ] **Step 4: Run** — `pytest tests/embed/test_constants.py -v` — all pass.

- [ ] **Step 5: Commit** — `git commit -m "feat(server): add embed-token + service-key constants"`

---

### Task 2: Settings env-var exposure

**Files:**
- Modify: `packages/python/awaithumans/server/core/config.py`
- Test: `packages/python/tests/embed/test_config.py`

- [ ] **Step 1: Failing test** — for each new field, monkeypatch the env var, reload `config.py`, assert `settings.<NAME>` matches. Tests: `EMBED_SIGNING_SECRET`, `AWAITHUMANS_EMBED_PARENT_ORIGINS`, `AWAITHUMANS_SERVICE_API_KEY` plus the default-None case.

- [ ] **Step 2: Run** — fails with AttributeError on Settings.

- [ ] **Step 3: Add fields to `class Settings(BaseSettings):`**:
  - `EMBED_SIGNING_SECRET: str | None = None`
  - `AWAITHUMANS_EMBED_PARENT_ORIGINS: str = ""`
  - `AWAITHUMANS_SERVICE_API_KEY: str | None = None`

  Add inline comments referencing the spec sections each field implements.

- [ ] **Step 4: Run** — pass.

- [ ] **Step 5: Commit** — `feat(server): expose embed env vars on Settings`

---

### Task 3: Embed exception classes

**Files:**
- Modify: `packages/python/awaithumans/server/services/exceptions.py`
- Test: `packages/python/tests/embed/test_exceptions.py`

- [ ] **Step 1: Failing test** — assert `InvalidEmbedTokenError(reason="bad sig")` is a `ServiceError`, has `status_code=401`, `error_code="invalid_embed_token"`, the reason is in the message. Likewise `EmbedOriginNotAllowedError(origin="https://evil.example")` → 400 / `embed_origin_not_allowed`. `ServiceKeyNotFoundError()` → 401 / `service_key_not_found`.

- [ ] **Step 2: Run** — ImportError fails.

- [ ] **Step 3: Append three classes** to `services/exceptions.py`, each subclassing `ServiceError` with the documented `status_code`, `error_code`, `docs_path = "/docs/embedding#..."`. Constructor takes the relevant kwargs and calls `super().__init__()` with the formatted message.

- [ ] **Step 4: Run** — pass.

- [ ] **Step 5: Commit** — `feat(server): add embed-related ServiceError subclasses`

---

## Phase 2 — Token signing + origin matching

### Task 4: `embed_token_service.sign_embed_token` / `verify_embed_token`

**Files:**
- Create: `packages/python/awaithumans/server/services/embed_token_service.py`
- Test: `packages/python/tests/embed/test_token_service.py`

- [ ] **Step 1: Failing tests** — write 7 tests covering: round-trip; tampered signature rejected; wrong audience rejected; `alg=none` rejected (force the header to base64 of `{"alg":"none","typ":"JWT"}` after encoding normally); expired token rejected; TTL clamp to MAX (3600); negative TTL raises ValueError. Use a dataclass `EmbedClaims` for the decoded shape.

- [ ] **Step 2: Run** — module-not-found fails.

- [ ] **Step 3: Implement** — `embed_token_service.py` exposes:

  - `@dataclass(frozen=True) class EmbedClaims` with fields `task_id, sub, kind, parent_origin, iat, exp, jti`.
  - `sign_embed_token(*, secret, task_id, sub, kind, parent_origin, ttl_seconds) -> tuple[token, exp_unix]`. Clamps TTL to `[MIN, MAX]`, raises `ValueError` on negative. Generates `jti` via `_ulid()` (timestamp ms + secrets.token_hex(8)). Calls `pyjwt.encode(...)` with `algorithm="HS256"`.
  - `verify_embed_token(token, *, secret) -> EmbedClaims`. Calls `pyjwt.decode(..., algorithms=["HS256"], audience=EMBED_TOKEN_AUDIENCE, issuer=EMBED_TOKEN_ISSUER, leeway=EMBED_TOKEN_LEEWAY_SECONDS)`. Catches `pyjwt.ExpiredSignatureError`, `InvalidAudienceError`, `InvalidIssuerError`, `InvalidAlgorithmError`, generic `PyJWTError` and re-raises as `InvalidEmbedTokenError(reason=...)`. Validates required claims present and `kind in ("end_user",)`.

- [ ] **Step 4: Run** — 7 pass.

- [ ] **Step 5: Commit** — `feat(server): embed-token sign/verify (HS256)`

---

### Task 5: Origin allowlist parsing + matching

**Files:**
- Modify: `packages/python/awaithumans/server/services/embed_token_service.py`
- Test: `packages/python/tests/embed/test_origin_matching.py`

- [ ] **Step 1: Failing tests** — covering each rule from spec §4.3:
  - Strip whitespace, drop empty entries
  - Reject path / trailing slash / double-wildcard / http-not-on-localhost
  - Allow http on `localhost`
  - Exact match
  - Wildcard matches one DNS label below apex (`*.acme.com` matches `app.acme.com`, not `acme.com`, not `a.b.acme.com`)
  - Scheme must match
  - Port must match (use `:8443`)

- [ ] **Step 2: Run** — fails on `parse_origin_allowlist` import.

- [ ] **Step 3: Append to `embed_token_service.py`**:
  - `class InvalidAllowlistEntryError(ValueError)`.
  - `parse_origin_allowlist(raw: str) -> tuple[str, ...]` — splits on comma, strips, validates each via `_validate_origin_entry`. Returns frozen tuple.
  - `_validate_origin_entry(s)` — uses `urllib.parse.urlparse`. Asserts no path/query/fragment, scheme in `{http, https}`, http only for localhost/127.0.0.1, max one wildcard, wildcard must be leading label, every label matches `^[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?$`.
  - `origin_in_allowlist(origin, allowlist)` — iterates allowlist; for each entry compares scheme + (port-with-default), then host. Wildcard host: strip `*.`, require origin host to end with `.<apex>` and the prefix label be a single non-empty DNS label.
  - Use `_default_port(scheme)` returning 443/80.

- [ ] **Step 4: Run** — 11 pass.

- [ ] **Step 5: Commit** — `feat(server): origin-allowlist parsing + matching`

---

## Phase 3 — Service keys

### Task 6: Migration `create_service_api_keys`

**Files:**
- Create: `packages/python/alembic/versions/<ts>_create_service_api_keys.py`

- [ ] **Step 1: Generate** — `alembic revision -m "create service_api_keys"` from `packages/python/`.

- [ ] **Step 2: Replace generated body** with `op.create_table("service_api_keys", ...)` containing columns: `id` (String 36, PK), `name` (String 80, NOT NULL), `key_hash` (String 64, NOT NULL, UNIQUE), `key_prefix` (String 12, NOT NULL), `created_at` (DateTime tz, NOT NULL, server_default CURRENT_TIMESTAMP), `last_used_at` (DateTime tz, nullable), `revoked_at` (DateTime tz, nullable). `downgrade()` calls `op.drop_table`.

- [ ] **Step 3: Roundtrip** — `alembic upgrade head && alembic downgrade -1 && alembic upgrade head` — clean.

- [ ] **Step 4: Commit** — `feat(server): migration for service_api_keys table`

---

### Task 7: SQLModel `ServiceAPIKey`

**Files:**
- Create: `packages/python/awaithumans/server/db/models/service_api_key.py`
- Modify: `packages/python/awaithumans/server/db/models/__init__.py`
- Test: `packages/python/tests/embed/test_service_key_model.py`

- [ ] **Step 1: Failing test** — round-trip: create in-memory engine, `SQLModel.metadata.create_all`, insert a `ServiceAPIKey(id="01HX", name="acme-prod", key_hash="a"*64, key_prefix="ah_sk_abcdef", created_at=now)`, `commit`, query back, assert fields match and `revoked_at is None`.

- [ ] **Step 2: Run** — ImportError.

- [ ] **Step 3: Implement model** — `class ServiceAPIKey(SQLModel, table=True)` with `__tablename__ = "service_api_keys"` and fields exactly matching the migration column types/lengths. `last_used_at` and `revoked_at` are `Optional[datetime] = None`.

- [ ] **Step 4: Re-export** — append `from awaithumans.server.db.models.service_api_key import ServiceAPIKey  # noqa: F401` to `db/models/__init__.py`.

- [ ] **Step 5: Run** — pass.

- [ ] **Step 6: Commit** — `feat(server): SQLModel for service_api_keys`

---

### Task 8: Service-key service module

**Files:**
- Create: `packages/python/awaithumans/server/services/service_key_service.py`
- Test: `packages/python/tests/embed/test_service_key_service.py`

- [ ] **Step 1: Failing tests** — 7 tests (in-memory SQLite session fixture):
  - `create_service_key(name="acme-prod")` returns `(raw, row)`; raw starts with `ah_sk_`, len > 20; `row.key_hash != raw`; `row.key_prefix == raw[:12]`; `row.name == "acme-prod"`.
  - `verify_service_key(raw)` round-trips to the row.
  - `verify_service_key("ah_sk_doesnotexist")` raises `ServiceKeyNotFoundError`.
  - revoking then verifying raises `ServiceKeyNotFoundError`.
  - `list_service_keys(include_revoked=False)` excludes revoked.
  - `list_service_keys(include_revoked=True)` includes revoked.
  - oversize name (> 80 chars) → `ValueError`.

- [ ] **Step 2: Run** — ImportError.

- [ ] **Step 3: Implement** — `service_key_service.py` exporting:
  - `create_service_key(session, *, name)` — validates length, generates `raw = "ah_sk_" + secrets.token_hex(20)`, computes `key_hash = sha256(raw).hexdigest()`, builds row with ULID id and `created_at = datetime.now(UTC)`, commits, returns `(raw, row)`.
  - `verify_service_key(session, raw_key)` — looks up by `key_hash`, raises if missing or revoked, updates `last_used_at = now`, commits, returns row.
  - `list_service_keys(session, *, include_revoked=False)` — order by `created_at`, filter `revoked_at IS NULL` unless flag.
  - `revoke_service_key(session, key_id)` — set `revoked_at = now` if currently null. Idempotent.
  - private `_hash(raw_key)` and `_ulid()` helpers.

- [ ] **Step 4: Run** — 7 pass.

- [ ] **Step 5: Commit** — `feat(server): service-key CRUD + verification`

---

### Task 9: Three CLI commands

**Files:**
- Create: `packages/python/awaithumans/cli/commands/create_service_key.py`
- Create: `packages/python/awaithumans/cli/commands/list_service_keys.py`
- Create: `packages/python/awaithumans/cli/commands/revoke_service_key.py`
- Modify: `packages/python/awaithumans/cli/main.py`
- Test: `packages/python/tests/embed/test_cli_service_keys.py`

- [ ] **Step 1: Failing test** — using `typer.testing.CliRunner`:
  - `create-service-key --name "acme-prod"` exits 0, output contains `ah_sk_` and `Save this key now`.
  - Sequence `create → list → revoke → list` — last list output excludes revoked entry.
  - Test bootstraps the DB via `init-db` and uses `monkeypatch.setenv("AWAITHUMANS_DATABASE_URL", f"sqlite:///{tmp_path}/db.sqlite")`.

- [ ] **Step 2: Run** — fails with "no such command".

- [ ] **Step 3: Implement command modules**.
  - `create_service_key.py`: imports `get_session` from `awaithumans.server.db.session` and `create_service_key as _create` from the service. Uses `typer.Option(..., "--name")`. After create, prints id/name and the raw key with a yellow "Save this key now — it will not be shown again" line.
  - `list_service_keys.py`: `typer.Option(False, "--all")`. Prints fixed-width header then row per key with status `"revoked"` or `"active"`.
  - `revoke_service_key.py`: `typer.Argument(...)`. Catches `ServiceKeyNotFoundError`, prints red error, exits 1.

- [ ] **Step 4: Register** — In `cli/main.py`, add three imports and three `app.command()(fn)` calls.

- [ ] **Step 5: Run** — 2 pass.

- [ ] **Step 6: Commit** — `feat(cli): create/list/revoke service-key commands`

---

## Phase 4 — Audit columns + middleware + endpoints

### Task 10: Audit `via` columns migration + model

**Files:**
- Create: `packages/python/alembic/versions/<ts>_add_audit_via_columns.py`
- Modify: `packages/python/awaithumans/server/db/models/audit_log.py`

- [ ] **Step 1: Generate** — `alembic revision -m "add audit via columns"`.

- [ ] **Step 2: Edit migration** — `op.add_column("task_audit_log", sa.Column("via", sa.String(20), nullable=True))`, same for `embed_sub` (256), `embed_jti` (64). Add partial index `task_audit_log_embed_jti_idx ON task_audit_log(embed_jti) WHERE embed_jti IS NOT NULL` (use both `postgresql_where` and `sqlite_where`). Backfill: `op.execute("UPDATE task_audit_log SET via = 'dashboard' WHERE via IS NULL")`. `downgrade` drops the index and three columns.

- [ ] **Step 3: Add columns to model** — in `audit_log.py` add three `Field(default=None, max_length=...)` lines for `via`, `embed_sub`, `embed_jti`.

- [ ] **Step 4: Roundtrip** — `alembic upgrade head && alembic downgrade -1 && alembic upgrade head` — clean.

- [ ] **Step 5: Commit** — `feat(server): audit-log gains via / embed_sub / embed_jti`

---

### Task 11: `EmbedAuthMiddleware`

**Files:**
- Create: `packages/python/awaithumans/server/core/embed_auth.py`
- Test: `packages/python/tests/embed/test_embed_auth_middleware.py`

- [ ] **Step 1: Failing tests** — wire a tiny `FastAPI()` with the new middleware and a `/probe` route returning `request.state.embed_ctx.task_id` (or `None`):
  - Valid bearer token → 200 with `task_id` set.
  - No `Authorization` header → 200 with `None`.
  - `Authorization: Basic ...` → 200 with `None` (non-bearer ignored).
  - `Authorization: Bearer not.a.jwt` → 401 with `error.code == "invalid_embed_token"`.

- [ ] **Step 2: Run** — ImportError.

- [ ] **Step 3: Implement `embed_auth.py`** — `class EmbedAuthMiddleware(BaseHTTPMiddleware)` with `__init__(app, *, secret_provider: Callable[[], str | None])`. In `dispatch`:
  - Default `request.state.embed_ctx = None`.
  - If `Authorization` header missing or doesn't start `bearer `, call_next.
  - Token starting `ah_sk_` → call_next (those are service keys, not embed tokens).
  - If `secret_provider()` returns falsy → call_next (embed disabled).
  - Verify via `verify_embed_token`; on `InvalidEmbedTokenError` return `JSONResponse(status_code=401, content={"error": {"code": "invalid_embed_token", "message": str(e)}})`.
  - On success, set `request.state.embed_ctx = claims`; call_next.
  - Export `get_embed_ctx(request)` accessor.

- [ ] **Step 4: Run** — 4 pass.

- [ ] **Step 5: Commit** — `feat(server): EmbedAuthMiddleware for bearer JWT verification`

---

### Task 12: Mint endpoint

**Files:**
- Create: `packages/python/awaithumans/server/schemas/embed.py`
- Create: `packages/python/awaithumans/server/routes/embed.py`
- Modify: `packages/python/awaithumans/server/app.py`
- Test: `packages/python/tests/embed/test_mint_endpoint.py`

- [ ] **Step 1: Failing tests** (depend on Task 15 conftest providing `client` and `service_key_raw` fixtures):
  - Unauthenticated POST → 401.
  - Valid request → 200; body has `embed_token`, `embed_url` ending `#token=<token>`, `expires_at`.
  - `parent_origin` not in allowlist → 400 / `embed_origin_not_allowed`.
  - Unknown `task_id` → 404.
  - `ttl_seconds: 999999` clamps successfully (no error).

- [ ] **Step 2: Skip run for now** — fixtures land in Task 15.

- [ ] **Step 3: Implement schemas** — `schemas/embed.py` with `EmbedTokenRequest` (task_id 1..64, optional sub max 256, parent_origin 1..256, optional ttl_seconds) and `EmbedTokenResponse` (embed_token, embed_url, expires_at).

- [ ] **Step 4: Implement route** — `routes/embed.py`:
  - `require_service_key` dependency: parse `Authorization: Bearer ah_sk_...`; allow self-host fallback to `settings.AWAITHUMANS_SERVICE_API_KEY`; otherwise call `verify_service_key(db, raw)`. Raises `ServiceKeyNotFoundError` on miss.
  - `@router.post("/api/embed/tokens", response_model=EmbedTokenResponse)`:
    - 503 if `EMBED_SIGNING_SECRET` unset.
    - Parse allowlist via `parse_origin_allowlist(settings.AWAITHUMANS_EMBED_PARENT_ORIGINS)`; reject with `EmbedOriginNotAllowedError` on mismatch.
    - `get_task(db, body.task_id)` — 404 if missing.
    - Call `sign_embed_token(...)`, build `embed_url = f"{base_url}/embed/{task_id}#token={token}"`, return response with ISO8601 `expires_at`.

- [ ] **Step 5: Wire route + middleware in `app.py`** — import `embed as embed_routes`, call `app.include_router(embed_routes.router)`. Add `EmbedAuthMiddleware` with `secret_provider=lambda: settings.EMBED_SIGNING_SECRET`.

- [ ] **Step 6: Commit** — `feat(server): mint endpoint POST /api/embed/tokens`

---

### Task 13: Existing routes accept embed auth

**Files:**
- Modify: `packages/python/awaithumans/server/routes/tasks.py`
- Modify: `packages/python/awaithumans/server/services/task_service.py`
- Test: `packages/python/tests/embed/test_route_authorization.py`

- [ ] **Step 1: Failing tests** (uses Task 15 fixtures):
  - `GET /api/tasks/tsk_seeded` with embed bearer → 200, returns the task.
  - `GET /api/tasks/<other_task>` with the same bearer → 403.
  - `POST /api/tasks/tsk_seeded/respond` with embed bearer → 200.
  - `GET /api/tasks` (list) with embed bearer → 401 or 403.

- [ ] **Step 2: Skip run for now** — fixtures land in Task 15.

- [ ] **Step 3: Modify `routes/tasks.py`** — at the top of `GET /api/tasks/{task_id}` and `POST /api/tasks/{task_id}/respond`, call `embed_ctx = get_embed_ctx(request)`. If set:
  - 403 if `embed_ctx.task_id != task_id`.
  - For GET: return the task.
  - For POST: pass `via="embed"`, `embed_sub=embed_ctx.sub`, `embed_jti=embed_ctx.jti` into the audit-write call.
  - Skip the cookie-auth path entirely on embed.

- [ ] **Step 4: Modify `task_service.py`** — `respond_to_task(...)` accepts kwargs `via: str = "dashboard"`, `embed_sub: str | None = None`, `embed_jti: str | None = None`. Pass into the `TaskAuditLog(...)` constructor.

- [ ] **Step 5: Run** — 4 pass (after Task 15 lands).

- [ ] **Step 6: Commit** — `feat(server): tasks routes accept embed bearer auth`

---

### Task 14: `/embed/*` response headers + auth path skip

**Files:**
- Modify: `packages/python/awaithumans/server/app.py`
- Modify: `packages/python/awaithumans/server/core/auth.py`
- Test: `packages/python/tests/embed/test_response_headers.py`

- [ ] **Step 1: Failing tests** — `GET /embed/anything` returns:
  - `Content-Security-Policy` containing `frame-ancestors`, `frame-src 'none'`, `default-src 'self'`, `connect-src 'self'`.
  - `Referrer-Policy: no-referrer`.
  - `Permissions-Policy` with `geolocation=()`, `microphone=()`, `camera=()`.
  - Anonymous request to `/embed/...` does NOT 302 to `/login`.

- [ ] **Step 2: Run** — fails (headers absent, redirect happens).

- [ ] **Step 3: Add `EmbedResponseHeadersMiddleware` in `app.py`** — `BaseHTTPMiddleware`. Skip if `request.url.path` doesn't start with `/embed`. Compute `ancestors = " ".join(parse_origin_allowlist(settings.AWAITHUMANS_EMBED_PARENT_ORIGINS)) or "'none'"`. Build full CSP string per spec §5.7. Set `Referrer-Policy`, `Permissions-Policy`, `X-Content-Type-Options: nosniff`. `app.add_middleware(...)` it.

- [ ] **Step 4: Skip cookie auth in `core/auth.py`** — top of `DashboardAuthMiddleware.dispatch`: `if request.url.path.startswith("/embed/"): return await call_next(request)`.

- [ ] **Step 5: Run** — 4 pass.

- [ ] **Step 6: Commit** — `feat(server): security headers on /embed/*; cookie auth skip`

---

## Phase 5 — Test scaffolding

### Task 15: Embed test conftest

**Files:**
- Create: `packages/python/tests/embed/conftest.py`

- [ ] **Step 1: Implement conftest** — fixtures (autouse for env, scope=function for isolation):

  - `db_url` — `f"sqlite:///{tmp_path}/embed.sqlite"` from `tmp_path`.
  - `env` (autouse) — monkeypatches `EMBED_SIGNING_SECRET="x"*32`, `AWAITHUMANS_EMBED_PARENT_ORIGINS="https://acme.com"`, `AWAITHUMANS_DATABASE_URL=db_url`.
  - `session` — creates engine, runs `SQLModel.metadata.create_all`, yields a `Session(engine)`.
  - `seeded_task` — inserts a `Task(id="tsk_seeded", ...)` row, returns it.
  - `other_task_id` — inserts a second task, returns its id.
  - `service_key_raw` — calls `create_service_key(session, name="acme-prod")`, returns the raw string.
  - `embed_token` — calls `sign_embed_token(secret="x"*32, task_id="tsk_seeded", sub="acme:user_4271", kind="end_user", parent_origin="https://acme.com", ttl_seconds=300)`, returns the token.
  - `sample_response` — `{"approved": True}`.
  - `client` — depends on `seeded_task` and `service_key_raw`, builds the app via `create_app()`, returns `TestClient(app)`.

- [ ] **Step 2: Run the full embed suite** — `pytest tests/embed/ -v` — every previously-skipped test now passes.

- [ ] **Step 3: Commit** — `test(embed): shared conftest with isolated DB + seeded fixtures`

---

## Phase 6 — Dashboard embed route

### Task 16: Embed layout

**Files:**
- Create: `packages/dashboard/app/embed/layout.tsx`

- [ ] **Step 1: Implement** — minimal layout that imports `../globals.css` and returns `<div className="min-h-screen bg-bg text-fg">{children}</div>`. No nav, no footer, no sidebar.

- [ ] **Step 2: Commit** — `feat(dashboard): minimal /embed layout`

---

### Task 17: Embed helpers (token + post-message + api)

**Files:**
- Create: `packages/dashboard/lib/embed/token.ts`
- Create: `packages/dashboard/lib/embed/post-message.ts`
- Create: `packages/dashboard/lib/embed/api.ts`

- [ ] **Step 1: `token.ts`** — `"use client"`. `extractEmbedToken()` reads `window.location.hash.replace(/^#/, "")` into `URLSearchParams` and returns the `token` param or null.

- [ ] **Step 2: `post-message.ts`** — `"use client"`. Discriminated union `EmbedEvent` with variants `loaded`, `task.completed`, `task.error`, `resize`. `postEmbed(parentOrigin, event)` calls `window.parent.postMessage({ source: "awaithumans", ...event }, parentOrigin)` after guarding `parentOrigin` truthy.

- [ ] **Step 3: `api.ts`** — `"use client"`. `embedFetch<T>(path, { token, ...init })`: builds URL from `window.__AWAITHUMANS_API_URL__ || "http://localhost:3001"` + path. Always sets `Content-Type: application/json` and `Authorization: Bearer ${token}`. On non-2xx, parses `{error: {code, message}}` and throws `EmbedFetchError(code, message)`. On 2xx, returns `await res.json() as T`.

- [ ] **Step 4: Commit** — `feat(dashboard): embed utilities — token, postMessage, api`

---

### Task 18: Embed page

**Files:**
- Create: `packages/dashboard/app/embed/[taskId]/page.tsx`

- [ ] **Step 1: Implement page** — `"use client"`. Component receives `params: { taskId }`. State: `token`, `task`, `value`, `submitting`, `error`. Ref: `parentOriginRef` (string).

  Effects:
  1. On mount: extract token via `extractEmbedToken()`. If null, set error and post `task.error` with code `invalid_token`. Otherwise decode JWT payload (split on `.`, base64-decode middle part, JSON.parse) — read `parent_origin` into the ref. (Server still verifies signature; this decode is only to know where to postMessage.)
  2. After token set: `embedFetch<TaskResponse>(/api/tasks/${taskId}, { token, method: "GET" })`. On success, set task and post `loaded`. On error, set error message and post `task.error`.
  3. ResizeObserver on `document.documentElement` posts `resize` with `scrollHeight` on every change. Disconnect on unmount.

  `onSubmit`: `embedFetch` to `/respond` with `JSON.stringify(value)`. On success post `task.completed` with the response payload and ISO timestamp. On error post `task.error`.

  Render: error pane if error; loading pane if no task; otherwise the task title + `<FormRenderer form={task.form} value={value} onChange={setValue} disabled={submitting} />` + a green "Submit" button calling `onSubmit`.

- [ ] **Step 2: Commit** — `feat(dashboard): /embed/[taskId] with postMessage + auto-resize`

---

## Phase 7 — SDKs

### Task 19: Python SDK helper

**Files:**
- Create: `packages/python/awaithumans/embed.py`
- Modify: `packages/python/awaithumans/__init__.py`
- Test: `packages/python/tests/embed/test_sdk_helper.py`

- [ ] **Step 1: Failing test** — using `pytest_httpx`'s `httpx_mock`:
  - Add response for `POST http://localhost:3001/api/embed/tokens` returning the standard JSON.
  - Call `embed_token_sync(task_id="tsk_01", sub="acme:u1", parent_origin="https://acme.com", api_key="ah_sk_test")`.
  - Assert `result.embed_token` and `"tsk_01" in result.embed_url`.

- [ ] **Step 2: Run** — ImportError.

- [ ] **Step 3: Implement `embed.py`**:
  - `@dataclass(frozen=True) class EmbedTokenResult` (`embed_token`, `embed_url`, `expires_at`).
  - `async def embed_token(*, task_id, sub=None, parent_origin, ttl_seconds=None, api_key, server_url=None)`. Build base URL from `server_url or env AWAITHUMANS_URL or "http://localhost:3001"`. POST JSON `{"task_id", "sub" (if not None), "parent_origin", "ttl_seconds" (if not None)}` with `Authorization: Bearer <api_key>`, 15s timeout. `raise_for_status`, return `EmbedTokenResult(**res.json())`.
  - `def embed_token_sync(**kwargs)` — `asyncio.run(embed_token(**kwargs))`.
  - `_refuse_browser_user_agent()` — if `"pyodide" in sys.modules` or `"js" in sys.modules`, write a warning to stderr. Called at the top of `embed_token`.

- [ ] **Step 4: Re-export** — `from awaithumans.embed import embed_token, embed_token_sync  # noqa: F401` in `__init__.py`.

- [ ] **Step 5: Run** — 1 pass.

- [ ] **Step 6: Commit** — `feat(sdk-py): embed_token / embed_token_sync helpers`

---

### Task 20: TypeScript SDK helper

**Files:**
- Create: `packages/typescript-sdk/src/types/embed.ts`
- Create: `packages/typescript-sdk/src/embed.ts`
- Modify: `packages/typescript-sdk/src/types/index.ts`
- Modify: `packages/typescript-sdk/src/index.ts`

- [ ] **Step 1: Types** — `types/embed.ts` exports `EmbedTokenOptions` (camelCase: `taskId`, `sub?`, `parentOrigin`, `ttlSeconds?`, `apiKey`, `serverUrl?`) and `EmbedTokenResult` (`embedToken`, `embedUrl`, `expiresAt`).

- [ ] **Step 2: Helper** — `src/embed.ts`:
  - `export async function embedToken(opts: EmbedTokenOptions): Promise<EmbedTokenResult>`.
  - If `globalThis.window !== undefined`, `console.warn("[awaithumans] service keys (ah_sk_...) must be server-side only.")`.
  - Build base from `opts.serverUrl || globalThis.process?.env?.AWAITHUMANS_URL || "http://localhost:3001"` with trailing-slash strip.
  - Translate camelCase opts → snake_case body keys (`task_id`, `parent_origin`, optional `sub`, optional `ttl_seconds`).
  - `fetch(\`${base}/api/embed/tokens\`, { method: "POST", headers: { "Content-Type": "application/json", Authorization: \`Bearer ${apiKey}\` }, body: JSON.stringify(body) })`.
  - On non-OK, parse error JSON and `throw new Error(err.error?.message || ...)`.
  - On OK, map `{embed_token, embed_url, expires_at}` → camelCase result.

- [ ] **Step 3: Re-export** — `types/index.ts` re-exports the embed types; `src/index.ts` adds `export { embedToken } from "./embed.js";`.

- [ ] **Step 4: Build verify** — `cd packages/typescript-sdk && npm run build` — clean.

- [ ] **Step 5: Commit** — `feat(sdk-ts): embedToken helper`

---

## Phase 8 — Examples + docs + verify

### Task 21: End-to-end Flask example

**Files:**
- Create: `examples/embed/server.py`
- Create: `examples/embed/index.html`
- Create: `examples/embed/README.md`

- [ ] **Step 1: `server.py`** — Flask app exposing `/` (serves index.html) and `/api/start-approval` which:
  - Calls `await_human_sync(task="Approve refund?", payload_schema=RefundReq, payload=RefundReq(amount=240, customer="cus_123"), response_schema=Decision, timeout_seconds=900)`.
  - Calls `embed_token_sync(task_id=task.id, sub="acme:demo_user", parent_origin="http://localhost:5000", api_key=os.environ["AH_SERVICE_KEY"])`.
  - Returns `jsonify({"approval_url": embed.embed_url})`.

- [ ] **Step 2: `index.html`** — minimal page with a "Start approval" button, a status div, and an iframe. Click handler fetches `/api/start-approval`, sets `iframe.src = approval_url`. `window.addEventListener("message", ...)` filters by `e.data?.source === "awaithumans"` and handles `loaded`, `resize` (sets iframe height), `task.completed`, `task.error`.

- [ ] **Step 3: `README.md`** — three-terminal walkthrough: (1) `awaithumans dev`, (2) `awaithumans create-service-key --name dev` + write `EMBED_SIGNING_SECRET` and `AWAITHUMANS_EMBED_PARENT_ORIGINS=http://localhost:5000` to `.env`, (3) `pip install flask awaithumans && AH_SERVICE_KEY=ah_sk_... python server.py` + open localhost:5000.

- [ ] **Step 4: Commit** — `docs(examples): end-to-end embed example`

---

### Task 22: Documentation page

**Files:**
- Create: `docs/embedding.md`

- [ ] **Step 1: Write** — sections:
  - Setup (self-host) — env vars, service-key creation
  - Mint an embed token — Python snippet
  - Drop the iframe — HTML snippet with postMessage handler
  - Events — table mirroring spec §4.5
  - Allowlisting — exact, wildcard, http-on-localhost rules
  - Security notes — five bullet points from spec §7.3
  - Errors — code reference
  - See also — links to the spec and example

- [ ] **Step 2: Commit** — `docs: embedding setup + reference`

---

### Task 23: Final verification

- [ ] **Step 1: Run all Python tests** — `cd packages/python && pytest tests/ -v` — full suite green; no regressions.

- [ ] **Step 2: Build dashboard** — `cd packages/dashboard && npm run build` — clean.

- [ ] **Step 3: Manual smoke test** — three terminals from the example README. Click "Start approval", confirm:
  - Iframe loads.
  - Console shows `loaded` event.
  - Submit form → console shows `task.completed` with response.
  - Awaithumans dashboard audit panel shows the row with `via=embed` and `embed_sub=acme:demo_user`.

- [ ] **Step 4: Done** — `git status` should be clean. PR description references the spec.

---

## Self-Review Checklist

- [ ] **Spec coverage:**
  - §3 architecture → Tasks 11, 12, 14
  - §4.1 URL fragment → Task 18 (extractEmbedToken)
  - §4.2 token claims → Task 4 (sign/verify) + Task 12 (mint endpoint)
  - §4.3 mint API → Task 12
  - §4.4 SDK helpers → Tasks 19, 20
  - §4.5 postMessage → Task 17 + Task 18
  - §4.6 reference example → Task 21
  - §5.1 EmbedAuthMiddleware → Task 11
  - §5.2 mint endpoint → Task 12
  - §5.3 service_api_keys table → Tasks 6, 7, 8
  - §5.4 env vars → Task 2
  - §5.5 route changes → Task 13
  - §5.6 audit migration → Task 10
  - §5.7 response headers → Task 14
  - §6 identity & audit → Task 13 + Task 10
  - §7 security model → covered structurally by Tasks 4 (alg pin), 11 (no cookie fallback), 14 (CSP/Referrer/Permissions), 5 (origin matching). Documented in Task 22.
  - §8 MVP scope → all in-scope items have tasks; out-of-scope items have no tasks.
  - §9 OSS / cloud positioning → Task 22 (docs); no separate code tasks (per-tenant cloud features deferred per spec).

- [ ] **Placeholder scan:** none (no TBD/TODO/FIXME).

- [ ] **Type consistency:**
  - `EmbedClaims` defined Task 4, used Tasks 11, 13.
  - `EmbedTokenResult` shape consistent across mint endpoint (Task 12), Python SDK (Task 19), TS SDK (Task 20).
  - `via` / `embed_sub` / `embed_jti` columns used identically in migration (Task 10), model (Task 10), service (Task 13), audit query expectations (manual verify Task 23).

- [ ] **Test files map to source files:** every new server source file has a matching test in `tests/embed/`. Dashboard files don't have unit tests in v1 (covered by manual smoke in Task 23) — acceptable per the spec's test posture; future iteration can add Playwright e2e.

---

## Execution Handoff

Plan complete and saved to
`docs/superpowers/plans/2026-05-06-dashboard-embedding.md`. Two
execution options:

1. **Subagent-Driven (recommended)** — fresh subagent per task, review between tasks, fast iteration. Best for this size (23 tasks across 8 phases).
2. **Inline Execution** — execute tasks in this session using executing-plans, batch execution with checkpoints.

Which approach?
