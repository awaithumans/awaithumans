/**
 * Slack installations — list + uninstall.
 */

import { ApiError, apiFetch } from "./client";

export interface SlackInstallation {
	team_id: string;
	team_name: string | null;
	bot_user_id: string;
	scopes: string;
	enterprise_id: string | null;
	installed_by_user_id: string | null;
	installed_at: string;
	updated_at: string;
}

export async function fetchSlackInstallations(): Promise<SlackInstallation[]> {
	return apiFetch<SlackInstallation[]>("/api/channels/slack/installations");
}

export async function uninstallSlackWorkspace(teamId: string): Promise<void> {
	await apiFetch<void>(
		`/api/channels/slack/installations/${encodeURIComponent(teamId)}`,
		{ method: "DELETE" },
	);
}

export interface SlackStaticWorkspace {
	team_id: string;
	team_name: string | null;
	bot_user_id: string | null;
}

/**
 * In static-token mode (SLACK_BOT_TOKEN env), no row exists in the
 * `slack_installations` table — so the dashboard would show "no
 * workspaces" even when Slack is fully configured. This endpoint
 * resolves the workspace behind the env token via Slack's
 * `auth.test` so the dashboard can render a read-only entry.
 *
 * Returns null when the server isn't in static-token mode (404 from
 * the API, mapped to null here for branching simplicity).
 */
export async function fetchStaticSlackWorkspace(): Promise<SlackStaticWorkspace | null> {
	try {
		return await apiFetch<SlackStaticWorkspace>(
			"/api/channels/slack/static-workspace",
		);
	} catch (err) {
		// 404 = not in static-token mode → null. Anything else (502
		// from Slack rejecting auth.test, network errors) bubbles up.
		if (err instanceof ApiError && err.status === 404) return null;
		throw err;
	}
}

export interface SlackMember {
	id: string;
	name: string;
	real_name: string | null;
	display_name: string | null;
	is_admin: boolean;
}

/**
 * Fetch active, human members of a Slack workspace. Powers the "pick a
 * Slack member" dropdown in the user-form — operators don't have to
 * remember or paste U... IDs.
 */
export async function fetchSlackWorkspaceMembers(
	teamId: string,
): Promise<SlackMember[]> {
	return apiFetch<SlackMember[]>(
		`/api/channels/slack/installations/${encodeURIComponent(teamId)}/members`,
	);
}
