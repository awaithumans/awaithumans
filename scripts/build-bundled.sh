#!/usr/bin/env bash
# Build the dashboard as a static export and drop it into the Python
# package so `pip install awaithumans[server] && awaithumans dev`
# serves API + UI on the same port.
#
# Steps:
#   1. Move `app/api/` aside (route handlers can't co-exist with
#      output: "export"). Restored on exit even on failure.
#   2. `next build` with AWAITHUMANS_STATIC_EXPORT=true and
#      NEXT_PUBLIC_AWAITHUMANS_BUNDLED=true (switches client.ts to
#      same-origin mode).
#   3. Wipe + copy `packages/dashboard/dist/` →
#      `packages/python/awaithumans/dashboard_dist/`. Hatchling picks
#      it up at wheel-build time (non-Python files inside a package
#      are auto-included).
#
# Run from the repo root (or anywhere — we resolve paths).

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DASHBOARD="$ROOT/packages/dashboard"
PY_PKG="$ROOT/packages/python/awaithumans"
DEST="$PY_PKG/dashboard_dist"
API_DIR="$DASHBOARD/app/api"
API_STASH="$DASHBOARD/app/_api_static_stash"

# Always restore the API dir — even on build failure or ^C.
cleanup() {
	if [ -d "$API_STASH" ]; then
		mv "$API_STASH" "$API_DIR"
	fi
}
trap cleanup EXIT

echo "→ building dashboard (static export, bundled mode)"

# Stash /api/discover — a route handler with dynamic="force-dynamic"
# breaks `output: export`. We keep the file for dev-mode use and
# restore on exit. Only dev mode needs it anyway; in bundled mode
# the dashboard is same-origin so discovery is trivially `""`.
if [ -d "$API_DIR" ]; then
	mv "$API_DIR" "$API_STASH"
fi

cd "$DASHBOARD"
rm -rf dist .next
AWAITHUMANS_STATIC_EXPORT=true \
	NEXT_PUBLIC_AWAITHUMANS_BUNDLED=true \
	npx next build

echo "→ copying dist/ → $DEST"
rm -rf "$DEST"
mkdir -p "$DEST"
cp -R "$DASHBOARD/dist/." "$DEST/"

echo "✓ dashboard bundled into $DEST"
echo "  ($(find "$DEST" -type f | wc -l | tr -d ' ') files)"
