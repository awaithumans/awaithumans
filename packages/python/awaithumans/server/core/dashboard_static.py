"""StaticFiles shim for Next.js static-export routing.

Next's `output: "export"` (without `trailingSlash: true`) emits a
layout like:

    dashboard_dist/
        setup.html         ← the actual page
        setup/             ← metadata directory (no index.html inside)

Stock `StaticFiles(html=True)` on request `/setup`:
  1. Looks for `setup` — finds the DIRECTORY (stat ≠ None).
  2. Being html-mode, tries `setup/index.html` — not there.
  3. Returns 404 — even though `setup.html` exists right next to it.

The subclass flips the priority: for extensionless clean URLs, try
`<path>.html` FIRST, only falling back to the normal behavior for
literal files (assets like `/favicon.ico`) and directories that
genuinely hold an `index.html`.

Covers the full dashboard surface (`/setup`, `/settings`, `/login`,
`/task`, `/audit`, `/analytics`) without changing Next's build
config, which would break dev-mode hot reload.
"""

from __future__ import annotations

import os
import stat as stat_module

from starlette.staticfiles import StaticFiles


class DashboardStaticFiles(StaticFiles):
    """StaticFiles that routes clean URLs to Next's flat HTML export.

    Starlette calls `lookup_path` in a worker thread via
    `anyio.to_thread.run_sync`, so this method is synchronous —
    don't make it async, or the super-call-chain breaks.
    """

    def lookup_path(  # type: ignore[override]
        self, path: str
    ) -> tuple[str, os.stat_result | None]:
        # For extensionless clean URLs, prefer `<path>.html` if it
        # exists. This matches Next's static-export output where
        # `setup.html` is the real page and `setup/` is a sibling
        # metadata directory without an index.html.
        last = path.rsplit("/", 1)[-1] if path else ""
        if path and last and "." not in last:
            html_full, html_stat = super().lookup_path(f"{path}.html")
            if html_stat is not None and stat_module.S_ISREG(html_stat.st_mode):
                return html_full, html_stat

        # Otherwise fall through to the stock behavior: literal file
        # match, then `<path>/index.html` for directories when html=True.
        return super().lookup_path(path)
