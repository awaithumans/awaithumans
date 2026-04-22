/**
 * User directory — list / create / update / delete + password mgmt.
 *
 * Admin-gated on the server: operator session OR admin bearer token.
 * The dashboard runs in operator-session mode (every call rides the
 * session cookie via `apiFetch`). The `password_hash` never crosses
 * the wire — `has_password` is the boolean we render.
 */

import { apiFetch } from "./client";

export interface User {
	id: string;
	display_name: string | null;

	email: string | null;
	slack_team_id: string | null;
	slack_user_id: string | null;

	role: string | null;
	access_level: string | null;
	pool: string | null;

	is_operator: boolean;
	has_password: boolean;

	active: boolean;
	last_assigned_at: string | null;

	created_at: string;
	updated_at: string;
}

export interface CreateUserRequest {
	display_name?: string | null;
	email?: string | null;
	slack_team_id?: string | null;
	slack_user_id?: string | null;
	role?: string | null;
	access_level?: string | null;
	pool?: string | null;
	is_operator?: boolean;
	password?: string | null;
	active?: boolean;
}

export type UpdateUserRequest = Partial<CreateUserRequest>;

export interface UserListFilters {
	role?: string;
	access_level?: string;
	pool?: string;
	active?: boolean;
}

function buildQuery(filters: UserListFilters | undefined): string {
	if (!filters) return "";
	const params = new URLSearchParams();
	if (filters.role) params.set("role", filters.role);
	if (filters.access_level) params.set("access_level", filters.access_level);
	if (filters.pool) params.set("pool", filters.pool);
	if (filters.active !== undefined) params.set("active", String(filters.active));
	const q = params.toString();
	return q ? `?${q}` : "";
}

export async function fetchUsers(filters?: UserListFilters): Promise<User[]> {
	return apiFetch<User[]>(`/api/admin/users${buildQuery(filters)}`);
}

export async function createUser(body: CreateUserRequest): Promise<User> {
	return apiFetch<User>("/api/admin/users", {
		method: "POST",
		body: JSON.stringify(body),
	});
}

export async function updateUser(
	id: string,
	body: UpdateUserRequest,
): Promise<User> {
	return apiFetch<User>(`/api/admin/users/${encodeURIComponent(id)}`, {
		method: "PATCH",
		body: JSON.stringify(body),
	});
}

export async function deleteUser(id: string): Promise<void> {
	await apiFetch<void>(`/api/admin/users/${encodeURIComponent(id)}`, {
		method: "DELETE",
	});
}

export async function setUserPassword(
	id: string,
	password: string,
): Promise<User> {
	return apiFetch<User>(
		`/api/admin/users/${encodeURIComponent(id)}/password`,
		{
			method: "POST",
			body: JSON.stringify({ password }),
		},
	);
}

export async function clearUserPassword(id: string): Promise<User> {
	return apiFetch<User>(
		`/api/admin/users/${encodeURIComponent(id)}/password`,
		{ method: "DELETE" },
	);
}
