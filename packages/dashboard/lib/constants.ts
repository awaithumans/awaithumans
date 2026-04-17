/**
 * Dashboard constants — all magic values centralized here.
 */

import type { TaskStatus } from "./types";

/** Polling interval for task list auto-refresh (milliseconds). */
export const TASK_LIST_POLL_INTERVAL_MS = 5000;

/** Default limit for the audit page task fetch. */
export const AUDIT_PAGE_DEFAULT_LIMIT = 100;

/** How many characters of a task ID to show in list views. */
export const TASK_ID_TRUNCATE_LENGTH = 12;

/** How many characters of an idempotency key to show in the detail view. */
export const IDEMPOTENCY_KEY_DISPLAY_LENGTH = 16;

/** Seconds per minute — used when formatting timeouts for humans. */
export const SECONDS_PER_MINUTE = 60;

/**
 * Default API server URL when neither the env override nor the discovery
 * file can resolve one. Must match the Python server's default bind port
 * (see awaithumans/utils/constants.py).
 */
export const DEFAULT_API_URL = "http://localhost:3001";

/** Under this many options, single-select renders as radio buttons; over, a dropdown. */
export const SELECT_RADIO_THRESHOLD = 4;

/** Signature pad canvas dimensions (logical pixels before device scaling). */
export const SIGNATURE_CANVAS_WIDTH = 600;
export const SIGNATURE_CANVAS_HEIGHT = 160;

/** Terminal task statuses — tasks in these states are done. */
export const TERMINAL_STATUSES: readonly TaskStatus[] = [
	"completed",
	"timed_out",
	"cancelled",
	"verification_exhausted",
] as const;

/** Docs base URLs. */
export const DOCS_BASE_URL = "https://awaithumans.dev/docs";
export const DOCS_TROUBLESHOOTING_URL = `${DOCS_BASE_URL}/troubleshooting`;
