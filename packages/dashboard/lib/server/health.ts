/**
 * Server health check.
 */

import type { HealthResponse } from "@/lib/types";
import { apiFetch } from "./client";

export async function fetchHealth(): Promise<HealthResponse> {
	return apiFetch<HealthResponse>("/api/health");
}
