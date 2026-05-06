/**
 * Project-wide constants for the TypeScript SDK.
 *
 * All magic numbers live here. Import from here, not from individual files.
 */

/** Minimum timeout in milliseconds (1 minute). */
export const MIN_TIMEOUT_MS = 60_000;

/** Maximum timeout in milliseconds (30 days). */
export const MAX_TIMEOUT_MS = 2_592_000_000;

/** Default server URL when no explicit override or env var is set. Must match
 *  the Python server's default bind port. */
export const DEFAULT_SERVER_URL = "http://localhost:3001";

/** How long each long-poll request holds the connection before reconnecting,
 *  in seconds. Matches the Python SDK; stays safely under typical 30s/60s
 *  gateway timeouts so intermediate proxies don't kill the socket. */
export const POLL_INTERVAL_SECONDS = 25;

/** Extra headroom on the fetch timeout beyond the server's poll window —
 *  gives the socket time to close cleanly before we abort. */
export const POLL_FETCH_SLACK_SECONDS = 10;

/** Timeout for the initial `POST /api/tasks` request. */
export const CREATE_TASK_TIMEOUT_MS = 30_000;

/** Docs base URLs for error messages. */
export const DOCS_BASE_URL = "https://awaithumans.dev/docs";
export const DOCS_TROUBLESHOOTING_URL = `${DOCS_BASE_URL}/troubleshooting`;
export const DOCS_ROADMAP_URL = `${DOCS_BASE_URL}/roadmap`;
