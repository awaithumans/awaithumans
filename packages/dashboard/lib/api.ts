/**
 * API client for the awaithumans server.
 *
 * The dashboard talks to the Python FastAPI server via HTTP.
 * Server URL defaults to localhost:3001 in dev.
 */

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:3001";

export interface Task {
	id: string;
	idempotency_key: string;
	task: string;
	payload: Record<string, unknown> | null;
	payload_schema: Record<string, unknown>;
	response_schema: Record<string, unknown>;
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
	metadata: Record<string, unknown> | null;
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

// ─── API Functions ──────────────────────────────────────────────────────

async function apiFetch<T>(path: string, options?: RequestInit): Promise<T> {
	const res = await fetch(`${API_BASE}${path}`, {
		...options,
		headers: {
			"Content-Type": "application/json",
			...options?.headers,
		},
	});

	if (!res.ok) {
		const body = await res.text();
		throw new Error(`API error ${res.status}: ${body}`);
	}

	return res.json() as Promise<T>;
}

export async function fetchTasks(params?: {
	status?: TaskStatus;
	assigned_to?: string;
	limit?: number;
	offset?: number;
}): Promise<Task[]> {
	const searchParams = new URLSearchParams();
	if (params?.status) searchParams.set("status", params.status);
	if (params?.assigned_to) searchParams.set("assigned_to", params.assigned_to);
	if (params?.limit) searchParams.set("limit", String(params.limit));
	if (params?.offset) searchParams.set("offset", String(params.offset));

	const query = searchParams.toString();
	return apiFetch<Task[]>(`/api/tasks${query ? `?${query}` : ""}`);
}

export async function fetchTask(taskId: string): Promise<Task> {
	return apiFetch<Task>(`/api/tasks/${taskId}`);
}

export async function completeTask(
	taskId: string,
	body: CompleteTaskRequest,
): Promise<Task> {
	return apiFetch<Task>(`/api/tasks/${taskId}/complete`, {
		method: "POST",
		body: JSON.stringify(body),
	});
}

export async function cancelTask(taskId: string): Promise<Task> {
	return apiFetch<Task>(`/api/tasks/${taskId}/cancel`, {
		method: "POST",
	});
}

export async function fetchAuditTrail(taskId: string): Promise<AuditEntry[]> {
	return apiFetch<AuditEntry[]>(`/api/tasks/${taskId}/audit`);
}

export async function fetchHealth(): Promise<HealthResponse> {
	return apiFetch<HealthResponse>("/api/health");
}
