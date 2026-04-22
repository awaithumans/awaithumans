/**
 * Auth API — login, logout, session introspection, first-run setup.
 *
 * All of these call the Python server's /api/auth/* or /api/setup/*
 * routes. credentials: "include" on the underlying apiFetch means the
 * session cookie the server sets on login comes back on subsequent
 * calls.
 */

import { apiFetch } from "./client";

export interface MeResponse {
	authenticated: boolean;
	user_id: string | null;
	email: string | null;
	display_name: string | null;
	is_operator: boolean;
}

export async function fetchMe(): Promise<MeResponse> {
	return apiFetch<MeResponse>("/api/auth/me");
}

export async function login(email: string, password: string): Promise<void> {
	await apiFetch<void>("/api/auth/login", {
		method: "POST",
		body: JSON.stringify({ email, password }),
	});
}

export async function logout(): Promise<void> {
	await apiFetch<void>("/api/auth/logout", {
		method: "POST",
	});
}

// ─── First-run setup ───────────────────────────────────────────────────

export interface SetupStatusResponse {
	needs_setup: boolean;
	token_active: boolean;
}

export async function fetchSetupStatus(): Promise<SetupStatusResponse> {
	return apiFetch<SetupStatusResponse>("/api/setup/status");
}

export async function createFirstOperator(args: {
	token: string;
	email: string;
	password: string;
	display_name?: string;
}): Promise<{ user_id: string; email: string }> {
	return apiFetch<{ user_id: string; email: string }>("/api/setup/operator", {
		method: "POST",
		body: JSON.stringify(args),
	});
}
