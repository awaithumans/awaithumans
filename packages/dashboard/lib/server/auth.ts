/**
 * Auth API — login, logout, session introspection.
 *
 * All three call the Python server's /api/auth/* routes. credentials:
 * "include" on the underlying apiFetch means the session cookie the
 * server sets on login comes back on subsequent calls.
 */

import { apiFetch } from "./client";

export interface MeResponse {
	authenticated: boolean;
	user: string | null;
	auth_enabled: boolean;
}

export async function fetchMe(): Promise<MeResponse> {
	return apiFetch<MeResponse>("/api/auth/me");
}

export async function login(user: string, password: string): Promise<void> {
	await apiFetch<void>("/api/auth/login", {
		method: "POST",
		body: JSON.stringify({ user, password }),
	});
}

export async function logout(): Promise<void> {
	await apiFetch<void>("/api/auth/logout", {
		method: "POST",
	});
}
