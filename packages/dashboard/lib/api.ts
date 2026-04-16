/**
 * API client for the awaithumans server.
 *
 * The dashboard talks to the Python FastAPI server via HTTP.
 * All type definitions live in lib/types.ts, not here.
 *
 * Server URL is discovered via /api/discover on first use, so the dashboard
 * auto-finds the Python server regardless of which port it bound to.
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

// ─── API base URL discovery ─────────────────────────────────────────────

const CACHE_TTL_MS = 30_000;
let cachedApiBase: string | null = null;
let cachedAt: number = 0;

function invalidateCache() {
	cachedApiBase = null;
	cachedAt = 0;
}

async function resolveApiBase(forceRefresh = false): Promise<string> {
	if (!forceRefresh && cachedApiBase && Date.now() - cachedAt < CACHE_TTL_MS) {
		return cachedApiBase;
	}

	try {
		const res = await fetch("/api/discover");
		if (res.ok) {
			const data = (await res.json()) as { url: string; source: string };
			cachedApiBase = data.url.replace(/\/$/, "");
			cachedAt = Date.now();
			return cachedApiBase;
		}
	} catch {
		// Discovery route unreachable — fall through to default
	}

	cachedApiBase = "http://localhost:3001";
	cachedAt = Date.now();
	return cachedApiBase;
}

// ─── API Functions ──────────────────────────────────────────────────────

async function apiFetch<T>(path: string, options?: RequestInit): Promise<T> {
	let base = await resolveApiBase();

	const doFetch = (url: string) =>
		fetch(`${url}${path}`, {
			...options,
			headers: {
				"Content-Type": "application/json",
				...options?.headers,
			},
		});

	let res: Response;
	try {
		res = await doFetch(base);
	} catch (err) {
		// Network error (server gone, port closed) — invalidate cache, rediscover, retry once
		invalidateCache();
		base = await resolveApiBase(true);
		res = await doFetch(base);
	}

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
