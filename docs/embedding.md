# Embedding

Render the awaithumans task review form inside your own product, with
your own auth, in three pieces:

1. Your backend mints a short-lived embed token.
2. Your frontend drops the embed URL into an `<iframe>`.
3. Your frontend listens for `task.completed` via `postMessage`.

No awaithumans login screen, no awaithumans account for your users.

## Setup (self-host)

Add to your awaithumans server's environment:

```bash
AWAITHUMANS_EMBED_SIGNING_SECRET=$(openssl rand -hex 32)
AWAITHUMANS_EMBED_PARENT_ORIGINS=https://acme.com
```

Create a service key (this is the partner-side secret used to mint
embed tokens — treat it like a database password):

```bash
awaithumans create-service-key --name "acme-prod"
# → ah_sk_xK8...   (shown once; store securely)
```

## Mint an embed token (Python)

In your backend, after the agent calls `await_human(...)`:

```python
import os
from awaithumans import embed_token_sync

embed = embed_token_sync(
    task_id=task.id,
    sub=f"acme:{current_user.id}",   # any opaque per-user identifier
    parent_origin="https://acme.com",
    api_key=os.environ["AH_SERVICE_KEY"],
    ttl_seconds=300,                 # 5 min default; max 3600
)
return {"approval_url": embed.embed_url}
```

## Mint an embed token (TypeScript)

```ts
import { embedToken } from "awaithumans";

const embed = await embedToken({
  taskId: task.id,
  sub: `acme:${currentUser.id}`,
  parentOrigin: "https://acme.com",
  apiKey: process.env.AH_SERVICE_KEY!,
});
return { approvalUrl: embed.embedUrl };
```

## Drop the iframe

```html
<iframe id="approval" src="<embed_url>" allow="clipboard-write"></iframe>
<script>
window.addEventListener("message", (e) => {
  if (e.source !== document.getElementById("approval").contentWindow) return;
  if (e.data?.source !== "awaithumans") return;

  if (e.data.type === "resize") {
    document.getElementById("approval").style.height = e.data.payload.height + "px";
  }
  if (e.data.type === "task.completed") {
    // e.data.payload.response is the typed object the user submitted.
    continueAcmeFlow(e.data.payload.response);
  }
  if (e.data.type === "task.error") {
    handleError(e.data.payload.code, e.data.payload.message);
  }
});
</script>
```

## Events

| `type` | When | `payload` |
|---|---|---|
| `loaded` | Iframe rendered, ready | `{ taskId }` |
| `task.completed` | User submitted, server accepted | `{ taskId, response, completedAt }` |
| `task.error` | Anything failed | `{ taskId, code, message }` |
| `resize` | Preferred height changed | `{ height }` |

Error codes: `INVALID_EMBED_TOKEN`, `EMBED_ORIGIN_NOT_ALLOWED`,
`SERVICE_KEY_NOT_FOUND`, `TASK_NOT_FOUND`, `TASK_ALREADY_TERMINAL`,
`internal`.

## Allowlisting

`AWAITHUMANS_EMBED_PARENT_ORIGINS` controls who can iframe the embed.
Examples:

```
https://acme.com                    # exact origin
https://*.acme.com                  # any single-label subdomain
http://localhost:3000               # dev only — http allowed on localhost
```

Multiple wildcards (`https://*.*.acme.com`) and trailing slashes are
rejected at server start. Schemes and ports must match exactly when
matching `parent_origin`.

## Security notes

- **Service keys are server-side only.** Never put `ah_sk_…` in browser
  code. Treat them like database passwords.
- **`task.payload` is visible to the embed user.** Don't put internal-
  only data, secrets, or PII the partner doesn't want exposed.
- **The `sub` claim is partner-controlled.** We record what you send;
  we don't verify it. You're responsible for accuracy.
- **Embeds require HTTPS in production.** Mixed content is blocked by
  browsers.
- **`parent_origin` must match the actual iframe parent exactly.**
  `https://app.acme.com` and `https://acme.com` are different origins.
- **The token in the URL fragment is not transmitted in HTTP requests
  or logged.** The iframe reads `location.hash` client-side and sends
  the token in the `Authorization` header.

## End-to-end example

See `examples/embed/` for a runnable Flask demo that creates a task,
mints an embed URL, and shows the postMessage handler in action.

## See also

- [Design spec](superpowers/specs/2026-05-06-dashboard-embedding-design.md) — full rationale.
- [Implementation plan](superpowers/plans/2026-05-06-dashboard-embedding.md).
