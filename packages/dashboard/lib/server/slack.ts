/**
 * Slack installations — list + uninstall.
 */

import { apiFetch } from "./client";

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
