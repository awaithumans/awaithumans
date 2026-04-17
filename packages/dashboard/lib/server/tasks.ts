/**
 * Task CRUD — list, fetch, complete, cancel.
 */

import type { CompleteTaskRequest, Task, TaskStatus } from "@/lib/types";
import { apiFetch } from "./client";

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
