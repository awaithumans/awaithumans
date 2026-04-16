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
