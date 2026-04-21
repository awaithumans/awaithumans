/**
 * Task stats — aggregates for the Analytics page.
 */

import { apiFetch } from "./client";

export interface TaskStatsByDay {
	date: string; // YYYY-MM-DD
	created: number;
	completed: number;
}

export interface TaskStats {
	window_days: number;
	generated_at: string;
	totals: Record<string, number>;
	completion_rate: number | null;
	avg_completion_seconds: number | null;
	by_day: TaskStatsByDay[];
	by_channel: Record<string, number>;
}

export async function fetchTaskStats(
	windowDays: number = 30,
): Promise<TaskStats> {
	return apiFetch<TaskStats>(`/api/stats/tasks?window_days=${windowDays}`);
}
