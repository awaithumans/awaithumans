/**
 * System status — diagnostic data for the Settings page.
 */

import { apiFetch } from "./client";

export interface SystemStatus {
	version: string;
	environment: string;
	public_url: string;
	auth_enabled: boolean;
	payload_encryption_enabled: boolean;
	admin_token_enabled: boolean;
	slack_mode: "off" | "single-workspace" | "multi-workspace";
	email_transport: string | null;
	email_from: string | null;
}

export async function fetchSystemStatus(): Promise<SystemStatus> {
	return apiFetch<SystemStatus>("/api/status");
}
