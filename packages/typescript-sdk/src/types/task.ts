/**
 * Task-shaped types — what the SDK consumes and produces.
 *
 * Mirrors `awaithumans/types/task.py` on the Python side. Keeping the
 * two in lockstep is what lets the cross-language documentation hold
 * up: `AwaitHumanOptions` reads the same in either tongue.
 */

import type { ZodType } from "zod";
import type { JsonSchema7Type } from "zod-to-json-schema";

import type { AssignTo } from "./routing";
import type { VerifierConfig, VerifierResult } from "./verification";

// ─── Core primitive ────────────────────────────────────────────────────

export interface AwaitHumanOptions<TPayload, TResponse> {
	/** Human-readable description of the task. */
	task: string;

	/** Zod schema for the payload — drives the UI the human sees. */
	payloadSchema: ZodType<TPayload>;

	/** The data sent to the human. Must conform to payloadSchema. */
	payload: TPayload;

	/** Zod schema for the response — drives the response form. */
	responseSchema: ZodType<TResponse>;

	/**
	 * Timeout in milliseconds. REQUIRED — no default.
	 * Min: 60,000 (1 minute). Max: 2,592,000,000 (30 days).
	 */
	timeoutMs: number;

	/** Who should handle this task. Optional — defaults to the server's default pool. */
	assignTo?: AssignTo;

	/** Notification channels. E.g., ["slack:#ops", "email:sara@co.com"]. */
	notify?: string[];

	/** AI verifier config — sent to the server for execution. Optional — no verifier = human answer trusted. */
	verifier?: VerifierConfig;

	/** Explicit idempotency key. Defaults to content hash (direct mode) or engine identity (durable adapters). */
	idempotencyKey?: string;

	/** If true, audit log hides the payload body. */
	redactPayload?: boolean;

	/** Server URL override. Defaults to AWAITHUMANS_URL env var or http://localhost:3001. */
	serverUrl?: string;
}

// ─── Task state machine ────────────────────────────────────────────────

export type TaskStatus =
	| "created"
	| "notified"
	| "assigned"
	| "in_progress"
	| "submitted"
	| "verified"
	| "completed"
	| "rejected"
	| "timed_out"
	| "cancelled"
	| "verification_exhausted";

export const TERMINAL_STATUSES: readonly TaskStatus[] = [
	"completed",
	"timed_out",
	"cancelled",
	"verification_exhausted",
] as const;

// ─── Task record ───────────────────────────────────────────────────────

export interface TaskRecord {
	id: string;
	idempotencyKey: string;
	task: string;
	payload: unknown;
	payloadSchema: JsonSchema7Type;
	responseSchema: JsonSchema7Type;
	status: TaskStatus;
	assignTo?: AssignTo;
	response?: unknown;
	verifierResult?: VerifierResult;
	createdAt: Date;
	updatedAt: Date;
	completedAt?: Date;
	timedOutAt?: Date;
	timeoutMs: number;
	redactPayload: boolean;
}
