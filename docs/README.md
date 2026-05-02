# awaithumans docs site

[Mintlify](https://mintlify.com)-powered docs at [awaithumans.dev](https://awaithumans.dev).

## Local preview

```bash
npm install -g mintlify
cd docs
mintlify dev
```

Browser opens at `http://localhost:3000`. Hot-reload on save.

## Adding a page

1. Create the `.mdx` file under the right folder (`concepts/`, `adapters/`, etc.).
2. Add the page to `mint.json`'s `navigation` array — pages don't auto-index.
3. Use Mintlify components (`<Note>`, `<Warning>`, `<CardGroup>`, `<CodeGroup>`, `<Tabs>`) where they help; raw markdown for everything else.

## Deploying

GitHub integration. Push to `main` → docs site auto-rebuilds. The `awaithumans/awaithumans` GitHub App is connected to a Mintlify project; that's where the deploy hooks live.

## Linting

Mintlify validates MDX + checks broken links on every deploy. To check locally:

```bash
mintlify broken-links
```

## File-cap

Pages are deliberately one MDX file each — no auto-generated content, no MDX-from-source generation in v0.1. Hand-written so the docs read coherently top-to-bottom.

For API reference (`/docs/api/*`), the OpenAPI spec is canonical (`/api/openapi.json` on a running server). The hand-written API pages here exist for the highest-traffic endpoints — `POST /api/tasks`, `GET /api/tasks/{id}/poll`, `POST /api/tasks/{id}/complete`. Long tail is in the spec.
