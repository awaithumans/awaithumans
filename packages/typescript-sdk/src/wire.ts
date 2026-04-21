/**
 * Wire protocol: request/response shapes exchanged with the Python server.
 *
 * The Python server uses snake_case JSON on the HTTP surface. The SDK
 * speaks camelCase internally (idiomatic TS). This file owns the
 * translation so the rest of the SDK doesn't have to think about it.
 *
 * Kept as plain `interface`s (not Zod schemas) — the server is the
 * source of truth for validation; the SDK trusts responses it receives
 * and only validates user inputs (payload/response against caller schemas).
 */

import type { TaskStatus } from "./types";

// ─── POST /api/tasks ─────────────────────────────────────────────────

export interface CreateTaskRequestWire {
	task: string;
	payload: unknown;
	payload_schema: unknown;
	response_schema: unknown;
	form_definition: unknown | null;
	timeout_seconds: number;
	idempotency_key: string;
	assign_to: unknown | null;
	notify: string[] | null;
	verifier_config: unknown | null;
	redact_payload: boolean;
	callback_url: string | null;
}

export interface CreateTaskResponseWire {
	id: string;
	status: TaskStatus;
	// The server returns the full TaskResponse on create, but the SDK
	// only needs the id — everything else comes back via poll.
}

// ─── GET /api/tasks/{id}/poll ────────────────────────────────────────

export interface PollResponseWire {
	status: TaskStatus;
	response: Record<string, unknown> | null;
	completed_at: string | null;
	timed_out_at: string | null;
	verification_attempt?: number;
}

// ─── Assignment translation ──────────────────────────────────────────

/**
 * Convert the caller-friendly `AssignTo` shape into the server's wire
 * format. Mirrors `awaithumans.client._serialize_assign_to`.
 */
export function serializeAssignTo(assignTo: unknown): unknown | null {
	if (assignTo == null) return null;
	if (typeof assignTo === "string") return { email: assignTo };
	if (Array.isArray(assignTo)) return { emails: assignTo };
	if (typeof assignTo === "object") return assignTo;
	return { value: String(assignTo) };
}
