/**
 * API client for the awaithumans server.
 *
 * The dashboard talks to the Python FastAPI server via HTTP.
 * All type definitions live in lib/types.ts, not here.
 */

import type {
	AuditEntry,
	CompleteTaskRequest,
	HealthResponse,
	Task,
	TaskStatus,
} from "./types";

// Re-export types so pages can import from "@/lib/api" for convenience
export type { AuditEntry, CompleteTaskRequest, HealthResponse, Task, TaskStatus };

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:3001";

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
