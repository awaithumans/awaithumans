/**
 * Project-wide constants for the TypeScript SDK.
 *
 * All magic numbers live here. Import from here, not from individual files.
 */

/** Minimum timeout in milliseconds (1 minute). */
export const MIN_TIMEOUT_MS = 60_000;

/** Maximum timeout in milliseconds (30 days). */
export const MAX_TIMEOUT_MS = 2_592_000_000;

/** Docs base URLs for error messages. */
export const DOCS_BASE_URL = "https://awaithumans.dev/docs";
export const DOCS_TROUBLESHOOTING_URL = `${DOCS_BASE_URL}/troubleshooting`;
export const DOCS_ROADMAP_URL = `${DOCS_BASE_URL}/roadmap`;
