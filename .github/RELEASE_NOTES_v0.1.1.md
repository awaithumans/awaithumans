# awaithumans v0.1.1 — patch release

First patch on top of [v0.1.0](https://github.com/awaithumans/awaithumans/releases/tag/v0.1.0). Two fixes from real-world install issues caught in the launch-day smoke test, plus a bundled-dependency security update. No API changes.

## Highlights

- 🔒 **Bundled Next.js bumped `16.2.3` → `16.2.6`** in the dashboard, clearing 13 GHSA advisories. Ships in the Python wheel; PyPI users get the fix on `pip install --upgrade awaithumans`.
- 📦 **TypeScript SDK peer-dep range widened** so `npm install awaithumans @langchain/langgraph` works against current upstream LangGraph (`1.x`), not just the older `0.2.x` line.
- 🤝 **Python and TypeScript now mono-version** at `0.1.1` — single version number across the stack.

## Upgrade

### Python

```bash
pip install --upgrade "awaithumans[server]==0.1.1"
# or whichever extras you use:
#   pip install --upgrade "awaithumans[temporal]==0.1.1"
#   pip install --upgrade "awaithumans[langgraph]==0.1.1"
#   pip install --upgrade "awaithumans[verifier-claude]==0.1.1"
```

### TypeScript

```bash
npm install awaithumans@0.1.1
# Or with peers if you're using the adapters:
#   npm install awaithumans@0.1.1 @temporalio/workflow @temporalio/client
#   npm install awaithumans@0.1.1 @langchain/langgraph
```

### Docker

```bash
docker pull ghcr.io/awaithumans/awaithumans:0.1.1
# Or use the floating tag:
docker pull ghcr.io/awaithumans/awaithumans:latest
```

## What changed

### Security

- **Dashboard: Next.js `16.2.3` → `16.2.6`** (PR #94). Clears 13 GHSA-tracked advisories in the bundled dashboard. The dashboard ships statically built inside the Python wheel, so this fix only reaches PyPI users via a republish — the Python bump in this release is the delivery vehicle.

### Fixed

- **TypeScript SDK: `@langchain/langgraph` peer-dep range widened** to `"^0.2.0 || ^1.0.0"` (was `"^0.2.0"`) (PR #93). Users on a fresh `npm install awaithumans @langchain/langgraph` would get current upstream (`1.x`) and hit `ERESOLVE` against the old pinned range. Verified the `interrupt(...)` API surface the adapter uses is signature-identical across both majors. No runtime code changed.

- **Python package version bumped `0.1.0` → `0.1.1`** (PR #95) so the bundled-Next.js security fix can be republished to PyPI. Mono-version with the TypeScript SDK.

## What didn't change

- **No API changes** — every public function signature in v0.1.0 still works identically in v0.1.1.
- **No breaking changes** — `pip install --upgrade` and `npm install awaithumans@latest` are safe drop-in upgrades.
- **No infrastructure changes** — same Docker image shape, same server boot sequence, same dashboard URL.

## Verify the upgrade landed

After upgrading the Python package:

```bash
python -c "import awaithumans; print(awaithumans.__version__)"
# → 0.1.1

awaithumans dev
# open http://localhost:3001 — the dashboard loads with the patched Next.js
```

After upgrading the TS package:

```bash
node -e "console.log(require('awaithumans/package.json').version)"
# → 0.1.1
```

## Links

- 📚 [Documentation](https://awaithumans.dev/docs)
- 🆕 [What's new](https://awaithumans.dev/docs/changelog)
- 🔒 Security disclosures: **security@awaithumans.dev**
- 💬 [Discord](https://discord.gg/awaithumans) · [GitHub Discussions](https://github.com/awaithumans/awaithumans/discussions)
- 🐛 [v0.1.0 → 0.1.1 full diff](https://github.com/awaithumans/awaithumans/compare/v0.1.0...v0.1.1)
