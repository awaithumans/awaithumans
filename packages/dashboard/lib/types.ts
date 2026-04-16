/**
 * Dashboard types — mirrors the Python API server's response models.
 *
 * Core type definitions live here. Form primitive types live in form-types.ts
 * (one file, twenty-seven field shapes) and are re-exported below.
 */

export * from "@/lib/form-types";
import type { FormDefinition } from "@/lib/form-types";

export interface Task {
	id: string;
	idempotency_key: string;
	task: string;
	payload: Record<string, unknown> | null;
	payload_schema: Record<string, unknown>;
	response_schema: Record<string, unknown>;
	form_definition: FormDefinition | null;
	status: TaskStatus;
	assign_to: Record<string, unknown> | null;
	assigned_to_email: string | null;
	response: Record<string, unknown> | null;
	verifier_result: Record<string, unknown> | null;
	verification_attempt: number;
	timeout_seconds: number;
	redact_payload: boolean;
	created_at: string;
	updated_at: string;
	completed_at: string | null;
	timed_out_at: string | null;
	completed_by_email: string | null;
	completed_via_channel: string | null;
}

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

export interface AuditEntry {
	id: string;
	task_id: string;
	from_status: string | null;
	to_status: string;
	action: string;
	actor_type: string;
	actor_email: string | null;
	channel: string | null;
	extra_data: Record<string, unknown> | null;
	created_at: string;
}

export interface CompleteTaskRequest {
	response: Record<string, unknown>;
	completed_by_email?: string;
	completed_via_channel?: string;
}

export interface HealthResponse {
	status: string;
	version: string;
}
