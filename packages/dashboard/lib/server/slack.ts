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
