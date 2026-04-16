# Build Notes

**Not documentation.** These are rough engineering notes — what's been
implemented, why, what's deferred, and what needs to be reworded for
real docs later. Organized by feature area so Future Us can find things
without digging through git log.

Keep entries terse. Capture the *why* and the *non-obvious*. Things
obvious from the code don't need to be here.

---

## 0. What exists today (landscape)

| Layer | Path | Status |
|---|---|---|
| Python SDK (`await_human`) | `packages/python/awaithumans/client.py` | ✅ Works end-to-end |
| Python server (FastAPI) | `packages/python/awaithumans/server/` | ✅ Core + Slack |
| Python CLI (`awaithumans dev`) | `packages/python/awaithumans/cli/` | ✅ Works |
| Form primitives | `packages/python/awaithumans/forms/` | ✅ 27 primitives, 72 tests |
| Dashboard (Next.js 16) | `packages/dashboard/` | ✅ Renders all primitives |
| Slack channel (single-workspace + OAuth) | `packages/python/awaithumans/server/channels/slack/` | ✅ Block Kit + webhook + OAuth |
| Email channel (multi-tenant sender identities + magic links) | `packages/python/awaithumans/server/channels/email/` | ✅ Resend + SMTP + magic-link one-click approval |
| TypeScript SDK | `packages/typescript-sdk/` | 🚧 HTTP client stubbed, not wired |
| — | — | — |
| Temporal adapter | `packages/python/awaithumans/adapters/temporal.py` | 🚧 Stub |
| LangGraph adapter | `packages/python/awaithumans/adapters/langgraph.py` | 🚧 Stub |
| Webhook callbacks | — | 🔴 Not started |
| `awaithumans slack:connect` wizard | — | 🔴 Deferred to post-launch |
| Slack multi-workspace OAuth install | `channels/slack/oauth_state.py` + `routes/slack.py` OAuth routes | ✅ Done |

End-to-end proof: quickstart example runs agent → server → dashboard,
human clicks Yes via Playwright, agent receives typed result. Task ID
`88afdfc2889f41f49373110348098fcb` is the one from the successful E2E run
before the feat/server-core merge.

---

## 1. Form primitives framework

### What it is

A bounded set of 27 form primitives that developers attach to their
Pydantic response schema via `Annotated`. The server stores the form
definition alongside the task; renderers (dashboard, Slack, email)
consume the same wire format and produce channel-specific output.

Authoring looks like:

```python
class WireApproval(BaseModel):
    approve: Annotated[bool, switch(label="Approve this wire?")]
    comment: Annotated[str | None, long_text(label="Reason")] = None
```

The `name` and `required` fields are filled in by `extract_form()` — the
developer never sets them by hand.

### The 27 primitives

- **Text**: `display_text`, `short_text` (+ email/url/phone/currency/number/password/plain subtypes), `long_text`, `rich_text`
- **Selection**: `switch`, `single_select`, `multi_select`, `picture_choice`
- **Numeric**: `slider`, `star_rating`, `opinion_scale`, `ranking`
- **Date/time**: `date`, `datetime`, `date_range`, `time`
- **Media (input)**: `file_upload`, `signature`
- **Media (display)**: `image`, `video`, `pdf_viewer`, `html`
- **Layout**: `section`, `divider`, `section_collapse`
- **Complex**: `table`, `subform`

### Why we kept things we originally deferred

First pass deferred `signature`, `rich_text`, `ranking`, `table`,
`subform`, and the ratings/scale primitives. Founder pushed back: those
are the fintech-HITL primitives — KYC doc review, compliance sign-offs,
batch transaction review. Pulled them into v1. The primitives we
genuinely cut (captcha, voice_recording, color_picker, location,
address, submission_picker, social_media_links) were cut on "not
HITL-shaped" grounds, not "too hard".

### Capability matrix

`forms/capabilities.py` is the single source of truth for which channel
can render which primitive. Each entry is `NATIVE` or `LINK_OUT`. If
**any** field in a form forces link-out in a channel, the whole form
falls back to "Complete in dashboard" in that channel. The developer's
typed-response contract is preserved either way — humans may complete
via dashboard or via the channel, and the SDK gets back the same shape.

| Primitive | Dashboard | Slack | Email (interactive) |
|---|---|---|---|
| All text/select/date/switch/media-input | ✅ | ✅ | mixed (mostly link-out) |
| `signature`, `ranking`, `rich_text`, `table`, `subform` | ✅ | ❌ link-out | ❌ link-out |
| `video`, `pdf_viewer`, `html` | ✅ | ❌ | ❌ |

### Wire format

```json
{
  "version": 1,
  "fields": [
    { "name": "approve", "kind": "switch", "label": "Approve this wire?",
      "required": true, "true_label": "Yes", "false_label": "No", ... },
    ...
  ]
}
```

Discriminated on `kind`. Stored on `tasks.form_definition` as a JSON
column. Passed verbatim from SDK → server → renderers. Version field
exists so we can migrate the schema later without a DB migration.

### Key files

- `forms/base.py` — `FormFieldBase` shared shape
- `forms/fields/*.py` — one file per category, class + DSL helper
- `forms/definition.py` — discriminated union + `FormDefinition`
- `forms/extract.py` — walks Pydantic model_fields, reads `Annotated` metadata
- `forms/infer.py` — fallback when no `Annotated` (bool→switch, Enum→single_select, etc.)
- `forms/capabilities.py` — matrix + `form_renders_in()`
- `types/form.py` — re-exports so `awaithumans.types` surface covers forms

### Tests

`tests/forms/` — 26 tests. Cover: construction + JSON roundtrip for every
primitive, Annotated extraction, required-from-Optional inference,
humanized-label fallback, capability matrix coverage, recursive walk
for `section_collapse` and `subform`.

### Deferred / future

- Response coercion helper that validates channel input against the form
  definition before the server calls `response_schema.model_validate()`.
  Currently each channel renderer has its own coerce logic — factor out
  a shared `coerce_response(form, channel_values, channel)` later.
- TypeScript equivalent in the TS SDK. Not urgent since the server
  serializes the FormDefinition and channel renderers live in Python.
  Needed when someone writes an agent in TS and wants rich IDE
  typing on the form primitives. Zod `.meta()` path sketched in an
  earlier discussion but not built.
- `reference_file`, `reference_url`, `reference_user` primitives — came
  up in the brainstorm as "things a HITL response often references back".
  Deferred until a concrete customer need.

---

## 2. Dashboard form renderer

### What it is

`<FormRenderer form={formDefinition} value={value} onChange={...} />` —
walks the FormDefinition and dispatches each field to a React component
keyed by `kind`. Replaces the previous JSON-schema-driven form in
`app/tasks/[id]/page.tsx`.

### Structure

```
components/form-renderer/
  index.tsx          # dispatcher + <FormRenderer> + initialValueFor()
  field-wrapper.tsx  # label + required marker + hint
  text.tsx           # display_text, short_text (7 subtypes), long_text, rich_text
  selection.tsx      # switch, single_select (radio/dropdown auto), multi_select, picture_choice
  numeric.tsx        # slider, star_rating, opinion_scale, ranking
  date-time.tsx      # date, datetime, date_range, time
  media.tsx          # file_upload (base64), signature (canvas), image, video, pdf_viewer, html
  layout.tsx         # section, divider, section_collapse
  complex.tsx        # table, subform
```

Each file exports named components like `SwitchRenderer`. The dispatcher
in `index.tsx` is one big `switch (field.kind)` — TypeScript narrows
`field` per branch so the renderer is strictly typed.

### Design decisions worth remembering

- **Baseline-then-upgrade for complex primitives.** `rich_text` is a
  textarea today (Tiptap comes later). `ranking` has ↑/↓ buttons
  (drag-drop later). `signature` is a hand-rolled `<canvas>`. The wire
  format is the contract — upgrading the editor later doesn't break the
  task record.
- **`html` primitive is rendered in a locked-down iframe.**
  `sandbox=""` denies scripts, same-origin, forms, and popups. We're
  not pulling DOMPurify until there's a concrete need for inline HTML
  with JavaScript.
- **`single_select` picks its widget from option count.** ≤4 options →
  radio buttons. >4 → dropdown. Same heuristic in the Slack renderer.
- **`multi_select`**: ≤10 → checkboxes. >10 → multi-select dropdown.
- **File upload stores base64 data URLs in the form value.** This
  doesn't scale past a few MB; when we wire up presigned uploads the
  wire shape (`[{ name, mime, size, data }]`) stays the same — `data`
  becomes a URL instead of inline base64.

### Wiring into the task detail page

- `page.tsx` calls `initialValueFor(task.form_definition)` to seed state.
- `onChange={setFormData}` updates in place.
- Submit button calls `completeTask(taskId, { response: formData, ... })`.
- If `task.form_definition` is missing (shouldn't happen with current
  SDK but old tasks might), the form block is simply hidden — no
  fallback rendering. Worth noting if we see the "empty form" bug.

### Deferred / future

- Real rich-text editor (Tiptap or Lexical) — phase 2.
- Drag-and-drop for `ranking` — phase 2.
- Validation surfacing: show min/max/required errors inline before
  submit (today we let the server bounce the request and surface the
  error banner).
- `file_upload` → presigned S3 / Supabase flow.
- Keyboard shortcuts for approve/reject (a/r).

### Tests

None yet for the React components. Dashboard has Vitest configured
(`npm run test`) but no form-renderer tests written. If we hit a bug
across a primitive, write a regression test for that primitive.

---

## 3. Form definition wiring (SDK → server → dashboard)

End-to-end path:

1. Developer writes response schema with `Annotated[..., primitive()]`.
2. SDK `client.py` calls `extract_form(response_schema)` and posts the
   JSON as `form_definition` on `POST /api/tasks`.
3. Server stores it in `tasks.form_definition` (JSON column, nullable).
4. `GET /api/tasks/{id}` returns it.
5. Dashboard loads it and passes to `<FormRenderer>`.
6. Slack renderer also loads it from the Task model.

### Key migrations

- Added `tasks.form_definition: dict | None` (JSON, nullable) to the
  `Task` SQLModel. No data migration needed — existing rows get NULL.
  When the schema tightens (if ever), handle NULL gracefully on read.

### Non-obvious bits

- `extract_form` sets `name` from the Pydantic attribute, **always
  overriding** whatever the DSL helper may have carried. This is why
  building a form by hand (bypassing extract) yields empty `name`
  fields and the capability error-reporter falls back to the primitive
  kind.
- Optional-ness is inferred from Pydantic: either `Optional[X]` or a
  default value. A field like `x: bool = False` is `required=False`.
- JSON schema on the wire is a Pydantic discriminated-union
  serialization. The server stores it as raw JSON and re-validates on
  read. Recursive primitives (`subform`, `section_collapse`) need
  `model_rebuild()` — we do that in `forms/definition.py`.

---

## 4. Slack channel

### What it is

Block Kit modal integration. A task with `notify=["slack:#channel"]`
posts an initial message with "Open in Slack" (native modal) and
"Review in dashboard" (link-out) buttons. Opening the modal renders the
form as a Block Kit view; submitting it coerces the values back into
the typed response and completes the task.

### Setup (copy for docs later)

1. Paste `packages/python/awaithumans/server/channels/slack/app_manifest.yaml`
   at <https://api.slack.com/apps> → "From an app manifest".
   **Replace `{{PUBLIC_URL}}` first** — Slack has to be able to POST to
   `{PUBLIC_URL}/api/channels/slack/interactions`.
2. Install the app to your workspace.
3. Env:
   - `AWAITHUMANS_SLACK_BOT_TOKEN=xoxb-...`
   - `AWAITHUMANS_SLACK_SIGNING_SECRET=...`
   - `AWAITHUMANS_PUBLIC_URL=https://your-server.example.com`
4. Restart server.
5. Add tasks with `notify=["slack:#channel-name"]` or `notify=["slack:@UUSERID"]`.

For local dev, Slack can't reach `localhost`. Use a tunnel:
`cloudflared tunnel --url http://localhost:3001` and set `PUBLIC_URL` to
the generated URL. `awaithumans dev --tunnel` is a planned convenience
(not built).

### Design decisions

- **Raw-body signature verification.** Slack signs the raw request body.
  FastAPI's form parsing consumes the body, so the route calls
  `await request.body()` FIRST, verifies the HMAC, THEN parses the
  `payload` field. The route is sequential, not decorator-based, on
  purpose. Timestamp max-age is 5 min (replay protection).
- **Block ID convention: `awaithumans:{field_name}`.** Lets the
  coercer find our blocks and ignore anything else Slack might include.
- **`callback_id` is a known constant** (`awaithumans.review_modal`)
  so the webhook routes view_submission by it.
- **`private_metadata` carries the task ID.** Slack round-trips this
  field as an opaque string — safe against tampering because we verify
  the request signature.
- **Notifications use FastAPI BackgroundTasks**, not asyncio.create_task
  or inline await. Runs AFTER the HTTP response is sent. A slow Slack
  API call doesn't block task creation; a Slack outage doesn't fail a
  successful task write.
- **Whole-form link-out when any primitive can't render.** No partial
  rendering. Means the "Open in Slack" button is hidden on tasks with
  a `signature` or `table` field; "Review in dashboard" is always
  present.
- **`picture_choice` loses its images in Slack.** Block Kit radio
  buttons don't support image options. Falls back to a plain
  `static_select` — labels carry the meaning. Not ideal; revisit if
  someone actually uses picture_choice with Slack as the primary
  channel.
- **`slider` → `number_input` in Slack.** Slack has no slider widget.
  Min/max respected; UX is degraded but functional.

### Per-primitive Block Kit mapping (rendered natively)

| Primitive | Block Kit element |
|---|---|
| switch | `radio_buttons` (Yes/No) |
| short_text plain | `plain_text_input` |
| short_text email | `email_text_input` |
| short_text url | `url_text_input` |
| short_text number / currency | `number_input` (decimals on for currency) |
| long_text | `plain_text_input` multiline |
| single_select ≤4 | `radio_buttons` |
| single_select >4 | `static_select` |
| multi_select ≤10 | `checkboxes` |
| multi_select >10 | `multi_static_select` |
| picture_choice | `static_select` / `multi_static_select` |
| date / datetime / time | `datepicker` / `datetimepicker` / `timepicker` |
| slider | `number_input` with bounds |
| star_rating | `static_select` with "★★★☆☆" labels |
| opinion_scale | `static_select` with numeric labels |
| file_upload | `file_input` |
| display_text | `section` (mrkdwn) |
| section | `header` + `context` |
| divider | `divider` |
| image | `image` |

All other primitives → `UnrenderableInSlack` exception. Caller is
expected to check `form_renders_in(form, "slack")` first.

### Key files

- `channels/slack/signing.py` — HMAC verify + max-age check
- `channels/slack/blocks.py` — `form_to_modal()` + `open_review_message_blocks()`
- `channels/slack/coerce.py` — `slack_values_to_response()`
- `channels/slack/client.py` — lazy `AsyncWebClient` singleton
- `channels/slack/notifier.py` — `notify_task()` — parses `slack:...` entries and posts
- `routes/slack.py` — `POST /api/channels/slack/interactions` — block_actions + view_submission
- `channels/slack/app_manifest.yaml` — for one-paste Slack app setup

### Tests

`tests/slack/` — 88 tests.
- `test_signing.py` (7) — valid sig, tampered body, wrong secret, stale ts, future ts, missing headers, non-integer ts.
- `test_blocks.py` (24) — modal skeleton, redact_payload, per-primitive element shape, UnrenderableInSlack for signature/ranking, link-out message shape.
- `test_coerce.py` (15) — per-primitive extraction, missing block → None, layout fields skipped.
- `test_oauth_state.py` (7) — round-trip, tamper, expiry, wrong secret, uniqueness, malformed input.
- `test_installation_service.py` (5) — upsert/update/list/delete/missing.
- `test_client_resolver.py` (9) — env vs installation, fallbacks, ambiguous multi-install case.
- `test_oauth_security.py` (9) — install-token gate, single-workspace lockout, state-cookie CSRF, URL-encoded redirects, happy-path install.
- `test_encryption.py` (12) — roundtrip, nonce randomness, wrong key, tampered ciphertext, bad base64, wrong version, missing key, malformed key, short key, transparent column encryption (raw SQL is ciphertext).

No integration test yet with a mocked `AsyncWebClient`. The view_submission
→ complete_task path is covered conceptually but not end-to-end. Add when
we have a repro for a real-world Slack edge case (e.g. user-scoped modals).

### Multi-workspace OAuth install

Two install modes, picked by which env vars are set:

- **Single-workspace self-hosted (simpler).** Set
  `AWAITHUMANS_SLACK_BOT_TOKEN=xoxb-...`. The server uses that one
  token for all Slack API calls. OAuth routes return 503.
- **Multi-workspace distribution.** Set `AWAITHUMANS_SLACK_CLIENT_ID`
  + `AWAITHUMANS_SLACK_CLIENT_SECRET` (leave `SLACK_BOT_TOKEN` unset).
  Admins visit `GET /api/channels/slack/oauth/start` → consent page →
  callback stores a row in `slack_installations` keyed by `team_id`.

#### Token resolution (`channels/slack/client.py`)

- `get_env_client()` — synchronous fallback; returns a client using
  `SLACK_BOT_TOKEN` or None.
- `get_client_for_team(session, team_id)` — installation first, env
  token fallback, None. Used by the interactivity webhook (every
  Slack payload carries `team.id`).
- `get_default_client(session)` — for outbound notifications where
  the notifier doesn't know the team:
    1. env token → use it
    2. exactly one installation → use it
    3. multiple installations → None + logged warning ("ambiguous")

#### OAuth state (CSRF protection)

Self-verifying signed state — `channels/slack/oauth_state.py`.
Avoids adding a table for short-lived OAuth nonces.

    state = urlsafe_b64(f"{nonce}:{ts}:{hmac_hex(nonce:ts, SIGNING_SECRET)}")

Reuses `SLACK_SIGNING_SECRET` — one secret, not two. Expires after
10 minutes (`SLACK_OAUTH_STATE_MAX_AGE_SECONDS`).

#### Routes

- `GET /api/channels/slack/oauth/start` → 302 to `slack.com/oauth/v2/authorize`
  with `client_id`, `scope`, signed `state`, `redirect_uri`.
- `GET /api/channels/slack/oauth/callback` → verify state → POST to
  `slack.com/api/oauth.v2.access` → upsert installation → redirect to
  `{PUBLIC_URL}/?slack_installed={team_name}` (or
  `?slack_oauth_error=X` on failure).

#### Schema additions

- `slack_installations` table (SQLModel). Primary key `team_id`.
  Stores `bot_token`, `bot_user_id`, `scopes`, `enterprise_id`,
  `installed_by_user_id`, timestamps. Re-installs upsert in place.

#### Security defenses (OAuth hardening pass)

Six vulnerabilities flagged in the audit after the initial OAuth
build-out; five fixed, one deferred with a note.

| Risk | Severity | Fix |
|---|---|---|
| Unprotected `/oauth/start` → anyone could install their workspace | 🔴 High | Required `?install_token=` matching `SLACK_INSTALL_TOKEN` (constant-time compare via `hmac.compare_digest`). Without the env var set, route returns 503. |
| `/oauth/start` reachable in single-workspace mode | 🟠 Med | 503 when `SLACK_BOT_TOKEN` is set — operator already picked static-token mode; OAuth must not run alongside it. |
| OAuth state not session-bound (HMAC valid for anyone) | 🟠 Med | State is now a double-submit cookie: `/start` sets an `httponly + Secure + SameSite=Lax` cookie scoped to `/api/channels/slack/oauth`; `/callback` requires the `state` query param to match the cookie (constant-time). Cookie deleted after success/failure (single-use). |
| Unencoded query params in redirects | 🟡 Low | All dynamic redirect URLs use `urlencode()`. `team.name` and error codes from Slack travel as proper query values, not raw concatenation. Error strings also capped at 100 chars. |
| HTTP `PUBLIC_URL` in production | 🟡 Low | Loud startup error when `ENVIRONMENT=production` and `PUBLIC_URL` doesn't start with `https://`. Tokens and OAuth state would otherwise transit in cleartext. |
| Bot tokens stored as plaintext | 🟡 Low | AES-256-GCM encryption at rest via `EncryptedString` SQLAlchemy TypeDecorator on the `bot_token` column. Key from `AWAITHUMANS_PAYLOAD_KEY` (32 raw bytes, base64). Fail-fast at boot if OAuth is enabled but no key is set. See §10 "Encryption at rest". |

Defenses-in-depth also added:

- `hmac.compare_digest` everywhere a secret is compared (install token,
  state cookie, webhook HMAC).
- Cookie path scoped to `/api/channels/slack/oauth` so it's never sent
  to any other route.
- OAuth-state cookie invalidated on both success and Slack-side failure.

Covered by `tests/slack/test_oauth_security.py` (9 tests).

#### Multi-tenant caveat (not yet resolved)

For the **hosted cloud** case (one awaithumans.dev serving many
customers), we still need: (a) per-customer API auth to identify
which tenant owns a task, and (b) routing from tenant → workspace
(today we pick "the single installation" which only works while
each deployment has one workspace). Add tenant routing when we
stand up the paid hosted dashboard — out of scope for self-hosted
launch.

The install-token gate is the v1 answer. It assumes the operator
keeps the token secret and shares it only with authorized admins.
For a public cloud, replace with real user auth + tenant-scoped
installations.

### Deferred / future

- `awaithumans slack:connect` CLI wizard. Today the user pastes the
  manifest + tokens by hand. Wizard should: open `api.slack.com`, walk
  through install, capture OAuth callback, write to `.env`.
- Ephemeral progress updates. When a human starts reviewing, post an
  ephemeral "X is looking at this" message to the channel. Nice-to-have,
  not critical.
- Thread-based notifications (post updates as replies to the initial
  message instead of new messages).
- Slack Events API for DM commands (`/awaithumans queue`).
- File upload via `file_input` currently captures metadata only
  (id, name, url_private). Actually downloading + storing the file
  server-side is follow-up work — the file URLs expire and require
  the bot token to re-fetch.
- Error responses on `view_submission`. Today we raise `HTTPException`
  which returns non-200 and shows a generic Slack error. Better: return
  `{"response_action": "errors", "errors": {"awaithumans:field": "msg"}}`
  to highlight specific fields.
- App Home tab ("here are your pending tasks").

---

## 5. Routing / notify string format

Shared parser lives in `server/channels/routing.py`. Both Slack and email
notifiers use it. See §9 "Email channel → Routing format" for the full
shape; one sentence summary here:

    <channel>[+<identity>]:<target>

- `slack:#channel` / `slack+T123456:#channel` — default vs specific workspace
- `slack:@UUSERID` — DM a user (Slack user ID, `U...` or `W...`; usernames no longer work in `chat.postMessage`)
- `email:alice@example.com` / `email+acme-prod:alice@example.com` — default vs specific sender identity

Typos are silent (unknown prefix → dropped with a log line). A typed
DSL (`channel=slack(channel="#...")`) will come later — the string
format stays as the wire protocol.

---

## 6. Server architecture

Documented in `CLAUDE.md` already, not worth duplicating. Notes that
belong here, not there:

- **Task state machine.** 11 statuses in `TaskStatus`. 4 terminal
  (`completed`, `timed_out`, `cancelled`, `verification_exhausted`).
  Stored in `utils/constants.TERMINAL_STATUSES_SET`. Any code that
  branches on terminality should use that set, not a hand-rolled list.
- **Partial unique index on idempotency_key.** Active tasks (non-terminal)
  must have unique keys. Terminal ones can repeat. Implemented in
  `db/models/task.py` via `sqlite_where` / `postgresql_where` on
  `Index`. Lets a developer retry a failed task with the same content
  without hitting a constraint error.
- **First-writer-wins completion.** `complete_task` does an atomic
  `UPDATE ... WHERE status NOT IN (terminal)` and checks `rowcount`.
  Raises `TaskAlreadyTerminalError` on loss — which can happen if the
  timeout scheduler fires between our SELECT and UPDATE.
- **Long-poll releases DB sessions.** The poll endpoint acquires a
  fresh session per 1-second check inside the loop. Holding a session
  open for 25 seconds would exhaust the pool under load.
- **Timeout scheduler uses indexed `timeout_at`.** We don't scan all
  tasks and filter in Python — the query is `WHERE timeout_at < now
  AND status NOT IN terminal`.

---

## 7. Testing

- `tests/forms/` — 26 tests. Primitives, extraction, inference, capabilities.
- `tests/slack/` — 88 tests. Signing, blocks, coercion, OAuth state, installation service, client resolver, OAuth security, encryption at rest.
- `tests/email/` — 60 tests. Routing, transport backends, identity service, magic links, renderer, admin + action routes.
- Full Python suite: **174 tests**, ~0.9s end-to-end, no network.
- No dashboard tests yet (Vitest configured, no tests written).
- No integration tests with real Slack API or real DB. DB tests use
  an in-memory SQLite; Slack is mocked.
- Playwright E2E lives outside the test suite (run by hand). One known
  passing run on the pre-merge branch exercising agent → server →
  dashboard → Yes click → typed response.

### Gaps worth flagging

- No test for the route-level `BackgroundTasks` firing `notify_task`
  after create_task. If that wiring regresses, tests won't catch it.
- No test for view_submission → complete_task with a mocked Slack
  client and a real DB session.
- No test that the form_definition written to the DB round-trips
  through `FormDefinition.model_validate(task.form_definition)`
  correctly for every primitive.

---

## 8. Encryption at rest

Lives in `server/core/encryption.py`. Wraps `cryptography.hazmat` AES-256-GCM
and exposes `EncryptedString` — a SQLAlchemy `TypeDecorator` that
encrypts on INSERT/UPDATE and decrypts on SELECT transparently.

### Wire format (per column value)

    base64( version(1) || nonce(12) || ciphertext || tag(16) )

- **version** — currently `0x01`. A different value on read raises
  `EncryptionKeyError` (no silent fallback — rotation needs an explicit
  key registry, not heuristics).
- **nonce** — fresh 12 random bytes per write. Same plaintext → different
  ciphertext every time.
- **tag** — GCM authentication tag. Any bit flip anywhere in the blob
  raises `InvalidTag` on decrypt.

### Key material

`AWAITHUMANS_PAYLOAD_KEY` — 32 raw bytes, base64-encoded (urlsafe or
standard, padded or not). Generate with:

    python -c 'import secrets; print(secrets.token_urlsafe(32))'

`_get_key()` validates the key once per process (lru_cached) and
rejects anything that doesn't decode to exactly 32 bytes. The decoder
pads to a multiple of 4 and tries urlsafe-b64 first, then strict
standard-b64 (`validate=True` — the default strips non-alphabet chars
silently, which can produce a wrong-sized key from a well-formed
urlsafe token; we don't want that).

### What's encrypted today

- `slack_installations.bot_token` — a DB dump alone is not enough to
  compromise a Slack workspace. Attacker must also have `PAYLOAD_KEY`.

### What's not yet encrypted (open scope)

- `tasks.payload` / `tasks.response` — can contain PII / financial data.
  The existing `redact_payload` flag only hides values from the list
  API response; it does not encrypt storage. A future pass should apply
  `EncryptedString` (or a JSON-aware variant) to these columns when
  `redact_payload=True`. Until then, treat `redact_payload` as a UI
  masking hint, not a security control.
- `verifier_result.reason` / audit `extra_data` — low-sensitivity, not
  worth encrypting in v1.

### Fail-fast at boot

`app.py` raises at startup when `SLACK_CLIENT_ID` is set but
`PAYLOAD_KEY` is not. We never want the case where OAuth is "working"
but tokens are silently landing in plaintext. A bad env file crashes
the server cleanly instead.

### Key rotation

Not built. When we add it:

1. Support multiple keys, indexed by version byte.
2. Store a registry of (`version → key`) in config.
3. `encrypt_str` always uses the newest; `decrypt_str` picks by version.
4. Background job re-encrypts all rows with the newest key on rotation.

Single-key v1 is honest about the constraint — there's no silent
fallback that might mask a rotation bug.

### Tests

`tests/slack/test_encryption.py` (12 tests): roundtrip, nonce
randomness, wrong key → InvalidTag, tampered bit → InvalidTag,
truncated ciphertext → EncryptionKeyError, bad base64, wrong version,
missing key, malformed key, short key, and end-to-end through the
ORM — raw SQL shows ciphertext, service returns plaintext.

---

## 9. Email channel

### What it is

Send task review requests via email, with one-click approval for simple
boolean/select primitives and a link-out to the dashboard for complex
forms. Supports **multi-tenant sender identities**: each tenant's
emails can go from *their* domain (with their SPF/DKIM), delivered
through their transport.

### Transport abstraction

`server/channels/email/transport/`. One `EmailTransport` protocol,
four backends:

| Backend | For |
|---|---|
| `resend` | Managed — API key only, no infra |
| `smtp` | Google Workspace, Office 365, self-hosted mail relays |
| `logging` | Dev mode — prints to stdout |
| `noop` | Tests |

Factory resolves a transport from either env config (`EMAIL_TRANSPORT`,
`RESEND_KEY`, `SMTP_HOST`…) or a DB identity row's `transport_config`.

### Multi-tenant sender identities

`EmailSenderIdentity` table — one row per configured sender. Keyed by
a slug (`"acme-prod"`, `"staging"`). Stores `from_email`, `from_name`,
`reply_to`, `transport`, and `transport_config` (SMTP creds / API keys)
**encrypted at rest** via the same `EncryptedString` type used for
Slack bot tokens. A DB dump alone never reveals provider credentials.

### Routing format

    <channel>[+<identity>]:<target>

- `email:alice@example.com` — use env-default identity
- `email+acme-prod:alice@example.com` — use stored identity "acme-prod"
- `slack:#channel` — default Slack workspace
- `slack+T123456:#channel` — specific Slack workspace

`+` is unambiguous as a prefix delimiter because it can't appear in
`"email"` or `"slack"`. It *can* appear after the `:` (tagged email
addresses like `alice+tag@acme.com`) — parse only looks for `+` in the
prefix portion.

Shared parser: `server/channels/routing.py`. Used by both Slack and
email notifiers. Same multi-tenant primitive across channels.

### Magic-link one-click approval

For tasks with a **single** `switch` or small (≤4 options)
`single_select`, the email embeds per-value buttons:

    Approve  →  {PUBLIC_URL}/api/channels/email/action/<token>
    Reject   →  {PUBLIC_URL}/api/channels/email/action/<different-token>

Token carries `(task_id, field_name, value, expiry)`, HMAC-signed with
a key **derived via HKDF-SHA256 from `PAYLOAD_KEY`** (salt
`"awaithumans-email-magic-links"`). Using HKDF gives us a
cryptographically distinct key from the encryption key without a
second env var. TTL 24 hours.

### Anti-prefetch (Outlook SafeLinks, Gmail image proxy, etc.)

Outlook SafeLinks and many mobile mail clients GET-prefetch every link
in an email. If clicking the URL directly completed the task, prefetch
would auto-approve requests.

**Defense:**

- `GET /api/channels/email/action/{token}` → renders a dark-mode
  HTML page with a **POST** form and two buttons: the action and a
  cancel link. The GET is idempotent; only the POST mutates state.
- `POST /api/channels/email/action/{token}` → verifies the token and
  calls `complete_task`. Returns a "Thanks" page.
- If the task is already terminal on either request: show a friendly
  "already completed" page, not a 500.
- Single-use is enforced by `TaskAlreadyTerminalError` in the service
  — no separate token-consumed table needed.

### Fall back to link-out when magic links don't apply

Any form that has zero input fields, multiple input fields, or a
primitive other than `switch` / `single_select(≤4)` gets just a
"Review in dashboard" link. The developer's typed-response contract
doesn't change — the human still submits the same dict.

### Admin CRUD for identities

`POST/GET/DELETE /api/channels/email/identities[/{id}]` — gated by
`AWAITHUMANS_ADMIN_API_TOKEN` via the `X-Admin-Token` header.
Constant-time compare (`hmac.compare_digest`).

**`transport_config` is never echoed back in API responses.** Even an
admin with the token can't read a stored API key or SMTP password out
of the system — creds go in on create/update, never come out. Prevents
wholesale credential exfiltration if the admin token is stolen. To
rotate a key, POST a new identity with the new creds.

Creating an identity validates the `transport_config` by building the
transport up-front. A bad key or missing SMTP host fails fast with a
400 on create, not later at send time.

### Security properties

| Concern | Defense |
|---|---|
| Email header injection via `to`, `subject`, `from`, etc. | Rejected at `EmailMessage.__post_init__` — CR or LF anywhere raises `ValueError` before any transport sees the value. |
| HTML injection from developer payload | `html.escape()` on every payload value + task title before rendering. |
| Bot-prefetch auto-actions | GET is pure-read, POST mutates. Standard web pattern. |
| Magic-link token tampering | HKDF-derived HMAC-SHA256, constant-time verify. |
| Magic-link replay | 24h expiry + task-already-terminal check. |
| Credential exfiltration via admin API | Transport configs write-only; API never returns them. |
| SMTP cleartext | Warns loudly in logs when neither TLS nor STARTTLS is configured. |
| Admin endpoint abuse | `AWAITHUMANS_ADMIN_API_TOKEN` with constant-time compare; 503 when unset. |

### Config (env)

    AWAITHUMANS_EMAIL_TRANSPORT=resend        # or smtp, logging, noop
    AWAITHUMANS_EMAIL_FROM="notifications@acme.com"
    AWAITHUMANS_EMAIL_FROM_NAME="Acme Tasks"
    AWAITHUMANS_EMAIL_REPLY_TO="support@acme.com"
    AWAITHUMANS_RESEND_KEY=re_...
    AWAITHUMANS_SMTP_HOST=smtp.gmail.com
    AWAITHUMANS_SMTP_PORT=587
    AWAITHUMANS_SMTP_USER=notifications@acme.com
    AWAITHUMANS_SMTP_PASSWORD=...
    AWAITHUMANS_SMTP_START_TLS=true
    AWAITHUMANS_ADMIN_API_TOKEN=...           # required for identity CRUD

### Key files

- `channels/email/transport/` — base + resend + smtp + logging + noop + factory
- `channels/email/magic_links.py` — HKDF-keyed HMAC token
- `channels/email/templates.py` — HTML + plain-text templates
- `channels/email/renderer.py` — build_notification_email (decides buttons vs link-out)
- `channels/email/notifier.py` — BackgroundTask entry from tasks route
- `channels/routing.py` — shared `channel[+identity]:target` parser
- `services/email_identity_service.py` — identity CRUD with encryption
- `db/models/email_sender_identity.py` — table
- `routes/email.py` — admin CRUD + magic-link action routes
- `core/admin_auth.py` — `require_admin` dep

### Tests (60)

- `tests/email/test_routing.py` (10) — parser correctness + edge cases
- `tests/email/test_transport.py` (14) — EmailMessage validation, header injection defense, per-backend send (incl. mocked Resend)
- `tests/email/test_identity_service.py` (5) — CRUD + encryption of `transport_config` (raw-SQL peek proves plaintext is never on disk)
- `tests/email/test_magic_links.py` (8) — sign/verify/tamper/expire, short TTL, malformed tokens, missing payload fields
- `tests/email/test_renderer.py` (13) — switch → 2 buttons, single_select 3 → 3 buttons, 5 options → link-out, multi-input → link-out, payload escaping, subject, tags
- `tests/email/test_admin_and_action_routes.py` (10) — admin gating (missing/wrong/unset), full identity lifecycle, bad transport config → 400, magic-link GET renders form (anti-prefetch), POST completes task, second POST is idempotent, `transport_config` never echoed back

Slack multi-tenant routing verified via existing `test_client_resolver.py`
(9 tests) — `slack+T12345:#channel` now picks that workspace; ambiguous
cases (no identity + multiple installs) still log a warning and skip.

---

## 10. Open questions / things to decide

- **Should `notify` become typed routing (`slack(channel="#ops")`)** or
  stay as strings? Strings are SDK-friendly across languages; typed
  gives IDE support. Leaning typed for the primary path, keep strings
  as escape hatch.
- **Should the capability matrix be per-form or per-field at submit time?**
  Today it's per-field. If someone wires a form with ONE `signature`
  field and expects Slack, the form goes dashboard-only — even though
  a native Slack signature *could* exist (e.g. via a follow-up
  web form link). Probably fine for v1; document the behavior loudly.
- **File upload: where does the file physically go?** Slack `file_input`
  keeps a ref; dashboard uploads base64 into the task record (which
  lives in the DB). Neither scales. Need a presigned-upload flow
  that's channel-agnostic.
- **Verification integration with forms.** The AI verifier runs against
  the `response` dict. Does it see `form_definition` too? If yes, it
  can enforce more than schema (e.g. "the signature field must not be
  empty"). Not currently wired.
- **Dashboard: should the "Open in Slack" button be shown on the
  dashboard's task detail page?** Currently no — dashboard just shows
  the form. But a human might prefer to complete in Slack even when
  they opened the dashboard link. Low-priority.

---

## Appendix: recent session highlights

**Round 1 (primitives + dashboard renderer):** decided on 27 primitives
after founder pushback on deferring fintech-relevant ones. Built
Python primitive classes + DSL helpers, extract_form, type inference,
capability matrix. Added `form_definition` column + wiring through
SDK/server/API. Built React renderers for all 27. Replaced the
JSON-schema form in the task detail page. 26 Python tests pass;
dashboard typechecks + builds.

**Round 2 (Slack channel):** Block Kit renderer for 17 natively
supported primitives. `UnrenderableInSlack` exception for the other
10 (caller is expected to check `form_renders_in` first). HMAC
signing verification with 5-min replay protection. Interactivity
route handles `block_actions` (opens modal) and `view_submission`
(coerces + completes). Notifier parses `slack:...` from `notify` and
posts initial message. FastAPI BackgroundTask ensures Slack outage
doesn't fail task creation. App manifest YAML for one-paste setup.
46 Slack tests pass.
