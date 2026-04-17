/**
 * Task audit trail.
 */

import type { AuditEntry } from "@/lib/types";
import { apiFetch } from "./client";

export async function fetchAuditTrail(taskId: string): Promise<AuditEntry[]> {
	return apiFetch<AuditEntry[]>(`/api/tasks/${taskId}/audit`);
}
