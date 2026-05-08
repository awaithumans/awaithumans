# Embed example

End-to-end demo of the awaithumans dashboard-embedding flow: a partner
Flask backend mints an embed token via the awaithumans Python SDK, drops
the resulting URL into an `<iframe>`, and listens for `task.completed`
via `postMessage`.

## Prereqs

Three terminals.

### 1. awaithumans server + dashboard

```bash
# In your awaithumans dev .env:
AWAITHUMANS_EMBED_SIGNING_SECRET=$(openssl rand -hex 32)
AWAITHUMANS_EMBED_PARENT_ORIGINS=http://localhost:5000
```

Then:

```bash
awaithumans dev
```

### 2. Mint a service key

```bash
awaithumans create-service-key --name dev
# → ah_sk_xxxxxxxx... (shown once — save it)
```

### 3. Partner backend

```bash
cd examples/embed
pip install flask awaithumans
AH_SERVICE_KEY=ah_sk_... python server.py
```

Open <http://localhost:5000> and click **Start approval**. The iframe
loads the awaithumans review form. Fill it in, submit — the page below
the iframe updates with the typed response, posted to the parent via
`postMessage`.

## What this shows

- Partner backend creates an awaithumans task with `await_human_sync(...)`.
- Partner backend mints an embed token with `embed_token_sync(...)`.
- Partner frontend drops `embed_url` into an `<iframe>`.
- The iframe posts `loaded`, `resize`, `task.completed` events back to
  the parent window with explicit `targetOrigin` (only the configured
  `parent_origin` receives them).
- The parent reads the typed `response` via `e.data.payload.response`.

## Files

- `server.py` — Flask backend (`GET /` serves index.html; `GET /api/start-approval` creates a task + embed URL).
- `index.html` — Static frontend with the iframe and `message` listener.
- `README.md` — You are here.

## See also

- [Spec](../../docs/superpowers/specs/2026-05-06-dashboard-embedding-design.md)
- [Implementation plan](../../docs/superpowers/plans/2026-05-06-dashboard-embedding.md)
