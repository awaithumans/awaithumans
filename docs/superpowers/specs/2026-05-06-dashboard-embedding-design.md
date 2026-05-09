# Dashboard Embedding — Design Spec

**Status:** Draft, pending review
**Date:** 2026-05-06
**Branch:** `feat/embed-dashboard`
**Owner:** Founder
**Related pillars:** [04-open-source.md](../../../../pillars/04-open-source.md), [07-monetization.md](../../../../pillars/07-monetization.md), [11-partnerships.md](../../../../pillars/11-partnerships.md) (in review)

---

## 1. Motivation

A class of awaithumans customers don't want to send their users to a separate
review dashboard — they want awaithumans's task review UI to render inside
their own product, branded as their own. Examples:

- A fintech that needs the customer to confirm a transaction inline, in
  the fintech's own app, without bouncing them to `awaithumans.cloud`.
- A SaaS tool that needs end-users to approve agent-suggested actions
  inside the tool's existing dashboard.
- A partner agency that wants to white-label awaithumans inside the
  consoles they ship to *their* customers.

The integration shape is iframe + bring-your-own auth. The partner mints a
short-lived token from their backend, drops an iframe into their frontend,
and the iframe renders the typed task review form for the user to complete
— all without the user having an awaithumans account.

This is the **Scale-tier driver** in cloud monetization (per Pillar 07) and
the **distribution lever** in Pillar 11: every embedded surface is a
passive surface for the awaithumans brand.

---

## 2. Goals & non-goals

### Goals

- A partner can embed a single awaithumans task review form inside their
  own product, behind their own auth, with one HTTP call from their
  backend and one `<iframe>` in their frontend.
- The end-user (the partner's customer) never sees an awaithumans login
  page, never gets an awaithumans account, never bounces to a different
  domain mid-flow.
- The integration is identical between self-host and cloud (one set of
  protocol primitives, two operational stories).
- Audit log captures who completed each task, attributed to the partner
  and the partner's user identifier — durable, queryable, exportable.
- Defaults are secure-by-default: closed allowlists, short TTLs, strict
  CSP, bearer-only auth, no cookie ambiguity.

### Non-goals (v1)

- Operator/queue embeds (`kind: "operator"`) — token shape supports it,
  route does not.
- Bidirectional postMessage (parent → iframe).
- White-label / theming — visible "powered by awaithumans" footer is OK
  for v1 and can be toggled later from a tenant setting.
- JWKS / RS256 / partner-signed JWTs — the embed-token format collapses
  cleanly into JWKS later when an Enterprise prospect asks.
- Token revocation list — short TTL is the revocation mechanism in v1.
- Service-key management UI in the dashboard — CLI-only for v1.
- Rate limiting per service key — defer to v1.1.

---

## 3. High-level architecture

```
PARTNER APP                         awaithumans                   awaithumans CLOUD/SERVER
─────────────                       ───────────                   ────────────────────────

[partner backend]                                                 ┌──────────────────────┐
  │                                                               │ POST /api/embed/     │
  │ awaitHuman()  ────────────► creates task ────────────────────►│      tokens          │
  │   returns taskId            (existing API)                    │ (mints HS256 JWT,    │
  │                                                               │  signed by per-tenant│
  │ POST /api/embed/tokens                                        │  EMBED_SIGNING_SECRET)│
  │   { taskId, sub, parent_origin, ttl }   ◄──{ embedToken } ────│                      │
  │                                                               │                      │
  ▼                                                               │ GET /embed/[taskId]  │
[partner frontend]                                                │ (headless route — no │
   <iframe                                                        │  shell, no login;    │
     src="https://awaithumans.cloud                               │  reads token from    │
            /embed/{taskId}#token={embedToken}"                   │  URL fragment;       │
     allow="..."                                                  │  verifies, renders   │
   />                                                             │  task review form)   │
   │                                                              │                      │
   ◄── postMessage({source, type, payload},                       │ Response headers:    │
                    parent_origin from claim)                     │   CSP frame-ancestors│
                                                                  │   per-tenant allow   │
                                                                  │   Referrer-Policy    │
                                                                  │   Permissions-Policy │
                                                                  └──────────────────────┘
```

### Three new components

1. **Embed mint endpoint** (`POST /api/embed/tokens`, FastAPI server).
   Authenticated by partner's service API key. Validates that `task_id`
   belongs to caller's tenant; signs and returns a short-lived JWT plus
   a pre-built embed URL.

2. **Headless embed route** (`/embed/[taskId]`, Next.js dashboard).
   New route segment with its own minimal layout. No nav, no sidebar,
   no footer. Reads token from URL fragment, calls the API with bearer
   auth, renders the same `<FormRenderer>` the regular dashboard uses,
   posts lifecycle events back to `window.parent` with the explicit
   `parent_origin` from the token claim.

3. **Per-tenant frame-ancestors allowlist.** Self-host: comma-separated
   env var. Cloud: per-tenant config row, settable via dashboard.
   Defaults closed.

### One change to existing components

- `DashboardAuthMiddleware` gets a path-based skip for `/embed/*` so
  anonymous iframe loads do not redirect to `/login`.
- `GET /api/tasks/{id}` and `POST /api/tasks/{id}/respond` accept a new
  `EmbedAuthMiddleware`-set request context, scoped to the task in the
  token's `task_id` claim.
- Existing audit row gets two new nullable columns (`embed_sub`, `embed_jti`)
  and one new value for the `via` column (`"embed"`).

---

## 4. Partner integration surface

### 4.1 Embed URL shape

```
https://awaithumans.cloud/embed/{taskId}#token=eyJ...
```

The token is in the **URL fragment**, not the query string. Fragments are
never sent to the server, never appear in access logs, never appear in
the `Referer` header on cross-origin subresource loads. The embed page
reads `location.hash` client-side and passes the token via
`Authorization: Bearer …` headers on its API calls.

`taskId` is in the path because it identifies the resource. Token in the
query (`?token=…`) is **rejected** — partners using the old query-style
URL get an error in the iframe ("token must be in URL fragment").

### 4.2 Token claims (HS256)

```json
{
  "iss": "awaithumans",
  "aud": "embed",
  "task_id": "tsk_01HX...",
  "sub": "acme:user_4271",
  "kind": "end_user",
  "parent_origin": "https://acme.com",
  "iat": 1715000000,
  "exp": 1715000300,
  "jti": "01HX..."
}
```

| Claim | Required | Notes |
|---|---|---|
| `iss` | yes | Always `"awaithumans"`. |
| `aud` | yes | Always `"embed"`. Verifier rejects tokens with other audiences. |
| `task_id` | yes | The task this token authorizes. |
| `sub` | optional | Partner's user identifier. Recorded in audit, never verified. Partner is responsible for accuracy and for namespacing (`acme:user_4271`). |
| `kind` | yes | v1 supports only `"end_user"`. Reserved values: `"operator"` (post-MVP). |
| `parent_origin` | yes | Origin the iframe will be embedded at. Used as the explicit `targetOrigin` for postMessage. |
| `iat` | yes | Issued-at, validated with ±60s tolerance. |
| `exp` | yes | Expiry. Maximum TTL: 3600s (1 hr). Default: 300s (5 min). |
| `jti` | yes | Unique token ID. Recorded in audit. Reserved for future denylist. |

### 4.3 Mint API

```http
POST /api/embed/tokens
Authorization: Bearer ah_sk_<service_key>
Content-Type: application/json

{
  "task_id":       "tsk_01HX...",
  "sub":           "acme:user_4271",
  "parent_origin": "https://acme.com",
  "ttl_seconds":   300
}
```

**Response 200:**

```json
{
  "embed_token":  "eyJ...",
  "embed_url":    "https://awaithumans.cloud/embed/tsk_01HX...#token=eyJ...",
  "expires_at":   "2026-05-06T18:30:00Z"
}
```

**Validation:**

- `task_id` must exist and belong to the same tenant as the service key.
- `parent_origin` must be a valid HTTPS origin (scheme + host + optional
  port; no path, no query, no trailing slash) and must match one of the
  tenant's configured `frame-ancestors` allowlist entries. Matching rules:
    - Exact entry (`https://app.acme.com`) matches that origin only.
    - Wildcard entry (`https://*.acme.com`) matches one DNS label
      below `acme.com` — `app.acme.com` and `staging.acme.com` match;
      `acme.com` and `a.b.acme.com` do not.
    - Multiple wildcards in one entry (`https://*.*.acme.com`) are
      rejected at allowlist save-time as ambiguous.
    - Schemes (`http` vs `https`) and ports must match exactly. No
      cross-scheme matching.
- `ttl_seconds`: optional, default 300, hard cap 3600.
- `sub`: optional, free-form string up to 256 chars.

### 4.4 SDK helpers

**Python:**

```python
from awaithumans import Client

client = Client(api_key="ah_sk_...")

embed = client.embed.token(
    task_id="tsk_01HX...",
    sub="acme:user_4271",
    parent_origin="https://acme.com",
)

# embed.embed_token, embed.embed_url, embed.expires_at
```

**TypeScript:**

```ts
import { createClient } from "awaithumans";

const client = createClient({ apiKey: "ah_sk_..." });

const embed = await client.embed.token({
  taskId: "tsk_01HX...",
  sub: "acme:user_4271",
  parentOrigin: "https://acme.com",
});
```

Both helpers refuse to run from a browser User-Agent in dev mode and emit
a console warning ("service keys are server-side only — never put
`ah_sk_*` in browser code").

### 4.5 postMessage protocol

One-way, iframe → parent. All events shaped:

```ts
{
  source: "awaithumans",
  type:   "loaded" | "task.completed" | "task.error" | "resize",
  payload: { ... }
}
```

The iframe always posts with the explicit `targetOrigin` from the token's
`parent_origin` claim. Browser silently drops the message if the actual
parent's origin doesn't match.

| Event | When | Payload |
|---|---|---|
| `loaded` | iframe rendered, ready for interaction | `{ taskId }` |
| `task.completed` | user submitted, server accepted | `{ taskId, response, completedAt }` |
| `task.error` | something failed | `{ taskId, code, message }` |
| `resize` | preferred height changed | `{ height }` |

Error codes: `invalid_token`, `expired_token`, `task_not_found`,
`task_already_completed`, `task_timed_out`, `network`, `internal`.

### 4.6 Reference partner integration (end-to-end)

```python
# Partner's backend — agent code
from awaithumans import await_human, Client
from pydantic import BaseModel

class RefundReq(BaseModel):
    amount: float
    customer: str

class Decision(BaseModel):
    approved: bool

# 1. Create the task. Returns task_id; does not block.
task = await await_human.create(
    task="Approve refund?",
    payload_schema=RefundReq,
    payload=RefundReq(amount=240, customer="cus_123"),
    response_schema=Decision,
    timeout_seconds=900,
)

# 2. Mint an embed token for this user.
client = Client(api_key=os.environ["AH_SERVICE_KEY"])
embed = client.embed.token(
    task_id=task.id,
    sub=f"acme:{current_user.id}",
    parent_origin="https://acme.com",
)

# 3. Hand `embed.embed_url` to the partner's frontend.
return {"approval_url": embed.embed_url}
```

```html
<!-- Partner's frontend -->
<iframe
  id="approval"
  src="<approval_url from backend>"
  allow="clipboard-write"
  style="width: 100%; border: 0;"
></iframe>

<script>
  window.addEventListener("message", (e) => {
    if (e.source !== document.getElementById("approval").contentWindow) return;
    if (e.data?.source !== "awaithumans") return;

    if (e.data.type === "resize") {
      document.getElementById("approval").style.height = e.data.payload.height + "px";
    }
    if (e.data.type === "task.completed") {
      // Continue the partner's flow.
      doSomething(e.data.payload.response);
    }
  });
</script>
```

---

## 5. Server-side changes

### 5.1 New auth middleware: `EmbedAuthMiddleware`

Recognises `Authorization: Bearer <token>` where the JWT decodes with
`aud: "embed"`. Verifies signature, audience, issuer, expiry; writes a
request-scoped auth context:

```python
EmbedAuthContext(
    kind="embed",
    task_id=...,
    sub=...,
    jti=...,
    tenant_id=...,
)
```

JWT verification uses an explicit allow-list of algorithms (`["HS256"]`)
and rejects every other `alg`, including `none`. `aud`, `iss`, and `exp`
are checked.

The middleware does **not** fall through to cookie auth on failure — it
either succeeds or sets context to anonymous. Routes decide whether to
require embed context, cookie context, or either.

### 5.2 New mint endpoint

```python
# server/routes/embed.py
@router.post("/api/embed/tokens", response_model=EmbedTokenResponse)
async def mint_embed_token(
    body: EmbedTokenRequest,
    tenant: TenantContext = Depends(require_service_key),
    db: Session = Depends(get_db),
) -> EmbedTokenResponse:
    ...
```

Pseudocode:

```
1. require_service_key — validates `Authorization: Bearer ah_sk_...`,
   loads the service key, scopes the request to its tenant.
2. Validate body.task_id belongs to tenant.
3. Validate body.parent_origin is in tenant's frame-ancestors allowlist
   (per the matching rules in §4.3).
4. Validate body.ttl_seconds in [60, 3600], default 300.
5. Generate jti (ULID), construct claims, HS256-sign with tenant's
   EMBED_SIGNING_SECRET.
6. Return { embed_token, embed_url, expires_at }.
7. Audit log: "embed_token.minted", { tenant_id, service_key_id, task_id, sub, jti }.
```

### 5.3 New table: `service_api_keys`

```sql
CREATE TABLE service_api_keys (
    id              UUID PRIMARY KEY,
    tenant_id       UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    name            TEXT NOT NULL,
    key_hash        TEXT NOT NULL UNIQUE,    -- SHA-256(raw key)
    key_prefix      TEXT NOT NULL,           -- first 12 chars, for display
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_used_at    TIMESTAMPTZ,
    revoked_at      TIMESTAMPTZ
);

CREATE INDEX service_api_keys_tenant_idx ON service_api_keys(tenant_id);
```

Key format: `ah_sk_<32-char-base32>`. Raw key shown once on creation.
Stored as SHA-256 hash. Self-host without a DB row falls back to
`AWAITHUMANS_SERVICE_API_KEY` env var (single key).

CLI:

```bash
awaithumans create-service-key --name "acme-prod"
# → ah_sk_xK8...   (shown once)

awaithumans list-service-keys
awaithumans revoke-service-key <id>
```

### 5.4 New env vars / config

| Var | Self-host | Cloud |
|---|---|---|
| `EMBED_SIGNING_SECRET` | required, ≥32 bytes random | per-tenant in DB; rotated via API |
| `AWAITHUMANS_EMBED_PARENT_ORIGINS` | comma-separated allowlist; default `'self'` (deny) | per-tenant in DB; default deny |
| `AWAITHUMANS_SERVICE_API_KEY` | optional; single self-host key | N/A; use the table |

### 5.5 Existing route changes

- `GET /api/tasks/{id}` — accept either cookie auth OR embed auth. If
  embed, scope query: only return the task if `id == ctx.task_id`.
- `POST /api/tasks/{id}/respond` — same. On success, write an audit
  row with `via="embed"`, `embed_sub=ctx.sub`, `embed_jti=ctx.jti`.
- All other API routes (list, audit, admin) reject embed auth.

### 5.6 Audit changes

Migration adds two nullable columns to the existing audit-log table:

```sql
ALTER TABLE task_audit_log
    ADD COLUMN via         TEXT,           -- "dashboard" | "embed" | "webhook" | "api"
    ADD COLUMN embed_sub   TEXT,
    ADD COLUMN embed_jti   TEXT;

CREATE INDEX task_audit_log_embed_jti_idx
    ON task_audit_log(embed_jti) WHERE embed_jti IS NOT NULL;
```

The `via` column is backfilled to `"dashboard"` for existing rows.

### 5.7 Response headers on `/embed/*`

Set on every response from the embed route:

```
Content-Security-Policy:
    default-src 'self';
    script-src 'self' 'unsafe-inline';
    style-src 'self' 'unsafe-inline';
    font-src 'self' https://fonts.gstatic.com;
    img-src 'self' data:;
    connect-src 'self';
    frame-src 'none';
    frame-ancestors <per-tenant allowlist>;
Referrer-Policy: no-referrer
Permissions-Policy: geolocation=(), microphone=(), camera=(), payment=()
X-Content-Type-Options: nosniff
```

`X-Frame-Options` is **not** set — CSP `frame-ancestors` supersedes it
on modern browsers and the two conflict in some legacy ones.

---

## 6. Identity & audit model

There is no awaithumans `User` row for an embed end-user. Their identity
is the `sub` claim — an opaque, partner-namespaced string. The partner is
responsible for what goes in it.

**Audit row written on `task.completed` via embed:**

```json
{
  "task_id":      "tsk_01HX...",
  "event":        "task.completed",
  "via":          "embed",
  "embed_sub":    "acme:user_4271",
  "embed_jti":    "01HX...",
  "occurred_at":  "2026-05-06T18:24:13Z",
  "payload_hash": "..."
}
```

**Surfaced in the operator dashboard:**

- Task detail page: "Completed via embed by `acme:user_4271` at 18:24:13"
  (instead of "Completed by [Operator]").
- Audit page filter: `via = embed`.
- Audit CSV export adds `via`, `embed_sub`, `embed_jti` columns.

**Explicitly not built (v1):**

- An "embed user" object with a profile page.
- Cross-task identity aggregation.
- PII scrubbing or hashing of `sub`. We record verbatim.

---

## 7. Security model

### 7.1 Threats addressed by design

| Threat | Mitigation |
|---|---|
| Token leak via server logs / Referer / clipboard | Token in URL fragment, never in query or path |
| postMessage exfiltration to malicious parent | Explicit `targetOrigin` from `parent_origin` claim |
| Clickjacking | CSP `frame-ancestors` per-tenant allowlist; default deny |
| JWT alg confusion | Explicit algorithm allowlist (`["HS256"]`); `aud`/`iss`/`exp` always checked |
| CSRF on respond endpoint | Bearer-only auth — Authorization header doesn't auto-attach cross-origin |
| Cookie-from-operator-session bleed-over | Embed middleware never falls through to cookie auth |
| Mint-endpoint DoS | Service-key-required; v1.1 will add per-key rate limits |
| Cross-tenant token reuse | Per-tenant signing secret in cloud; single-tenant in self-host |
| Audience confusion (session token in embed verifier) | `aud: "embed"` enforced |
| Long-TTL tokens | Hard cap at 3600s server-side; 300s default |
| Sensitive headers/permissions enabled in iframe | `Permissions-Policy` blocks geolocation, mic, camera, payment |
| Subresource leaks | Strict CSP; `Referrer-Policy: no-referrer` |
| Iframe iframing further pages | CSP `frame-src 'none'` |
| Mixed content | HTTPS enforced; documented in setup guide |

### 7.2 Residual risks (accepted for v1)

| Risk | Why accepted | Future mitigation |
|---|---|---|
| Token replay during TTL window | Short TTL bounds the window to ≤5 min default | Single-use binding (mark `jti` spent on first respond); `jti` denylist API |
| Subdomain takeover at partner | Outside our trust boundary; partner's responsibility | Documented in security notes |
| Service key leak by partner | Same as above; service keys are partner-side secrets | Per-key rate limits, anomaly detection on cloud |
| Stored XSS via task `payload` | FormRenderer relies on React's default JSX escaping for all payload fields | Implementation-time audit: confirm no raw-HTML rendering paths exist for payload data; v1 ships with a regression test asserting React-escaped output |

### 7.3 Documentation requirements

The setup guide and the partner integration doc must explicitly call out:

1. **Service keys are server-side only.** Treat them like database
   passwords. The SDK refuses browser User-Agents in dev mode.
2. **Anything in `task.payload` is visible to the embed user.** Do not
   put internal-only data, secrets, or PII the partner doesn't want to
   expose.
3. **The `sub` claim is partner-controlled and unverified.** We record
   verbatim. Partner is responsible for accuracy.
4. **Embeds require HTTPS.** Mixed content is blocked by browsers and
   the spec assumes both partner and awaithumans are HTTPS.
5. **`parent_origin` must match the actual iframe parent exactly.**
   `https://app.acme.com` and `https://acme.com` are different origins.

---

## 8. MVP scope

### In v1

- `/embed/[taskId]` route + minimal `app/embed/layout.tsx`.
- `EmbedAuthMiddleware` in the FastAPI server.
- `POST /api/embed/tokens` mint endpoint.
- `service_api_keys` table + CLI.
- `EMBED_SIGNING_SECRET` (per-tenant in cloud, env var in self-host).
- Per-tenant `frame-ancestors` allowlist.
- Token format with all claims listed in §4.2 — `parent_origin` and
  `jti` included now to avoid future migration.
- Token in URL fragment (never query/path).
- Response header bundle in §5.7.
- postMessage protocol with 4 events (`loaded`, `task.completed`,
  `task.error`, `resize`).
- Audit columns: `via`, `embed_sub`, `embed_jti`.
- Reuse of existing `<FormRenderer>` for the form itself.
- Python + TS SDK helpers — `client.embed.token(...)`.
- One end-to-end example in `examples/embed/`.
- Documentation page: `docs/embedding.md`.

### Deferred to post-MVP

- Operator/queue embed (`kind: "operator"`).
- Cancel button / `task.cancelled` event.
- Bidirectional postMessage (parent → child).
- Token revocation list (`jti` denylist) — short TTL is the v1 mechanism.
- White-label theming (CSS variable overrides via URL or postMessage).
- Service-key management UI in the dashboard.
- Per-key rate limits, per-key origin scoping.
- JWKS / RS256 / partner-signed JWTs.
- `awaithumans embed:test` CLI for offline iframe smoke testing.
- Anomaly detection on the cloud side (unusual mint patterns).

---

## 9. OSS / cloud positioning

Aligned with Pillar 04 (OSS earns trust) and Pillar 07 (never charge for
core, self-hosted, data export).

### Self-hosted gets the full primitive

- Embed route, middleware, mint endpoint, CSP, postMessage, SDK helpers,
  audit metadata.
- Single signing secret via `EMBED_SIGNING_SECRET`.
- Single allowlist via `AWAITHUMANS_EMBED_PARENT_ORIGINS`.
- CLI service-key management.
- Single-tenant by definition.

A self-hosting partner can fully embed and ship to production without
paying us. This is non-negotiable.

### Cloud-managed adds operational convenience

- Multi-tenant — per-tenant signing secret, allowlist, service keys.
- Dashboard UI for service-key management (post-MVP for v1.1).
- Allowlist editor with blocked-attempt history (post-MVP).
- Per-key rate limits and origin scoping (post-MVP).
- `jti` denylist + leak-incident playbook (post-MVP).
- JWKS / BYO-JWT for Enterprise (post-MVP, on demand).

### Pricing tier mapping (proposal — confirms with Pillar 07/11)

| Tier | Embed access |
|---|---|
| Self-hosted | Full primitive, single-tenant, BYO ops |
| Starter ($100/mo) | Not included |
| Growth ($500/mo) | 1 service key, 1 allowlisted origin, 5k embed tokens/mo |
| Scale ($2,000/mo) | Unlimited keys + origins, allowlist UI, leak playbook |
| Enterprise (custom) | + JWKS / BYO-JWT, white-label, custom-domain embeds |

---

## 10. Open questions

1. **Tenant model in self-host.** Self-host has been single-tenant. Embed
   formally introduces "tenant" as a concept (service keys belong to
   tenants). Self-host can stay single-tenant by treating the install
   as one implicit tenant — service keys all map to tenant `default`.
   This may cross-cut other features later (e.g., multi-team
   self-host). Confirmed scope is single-tenant for v1.
2. **Custom embed domain.** Cloud Enterprise will eventually want
   `embed.acme.com` instead of `awaithumans.cloud/embed/...`. This means
   per-tenant CNAME plus per-tenant TLS — outside v1.
3. **Pillar 11 alignment.** Pricing-tier inclusion (above) and the
   "powered by awaithumans" footer behavior need confirmation against
   Pillar 11 once that pillar is approved.
4. **Form schemas with file uploads.** The existing FormRenderer
   supports media fields. Cross-origin file uploads from an embed need
   testing — CORS pre-flight may add latency. Out of scope for spec but
   should be tested in v1 implementation.

---

## 11. References

- [Pillar 03 — Technical Architecture](../../../../pillars/03-architecture.md) — adapter buckets, server boundaries.
- [Pillar 04 — Open Source Strategy](../../../../pillars/04-open-source.md) — what stays MIT.
- [Pillar 07 — Monetization](../../../../pillars/07-monetization.md) — cloud tier model.
- [Pillar 11 — Partnerships & Ecosystem Distribution](../../../../pillars/11-partnerships.md) — distribution lever framing (in review).
- [CSP `frame-ancestors`](https://developer.mozilla.org/en-US/docs/Web/HTTP/Headers/Content-Security-Policy/frame-ancestors).
- [JWT Best Current Practices (RFC 8725)](https://www.rfc-editor.org/rfc/rfc8725) — algorithm allowlist, audience checking.
- [postMessage targetOrigin](https://developer.mozilla.org/en-US/docs/Web/API/Window/postMessage) — why `*` is unsafe.
