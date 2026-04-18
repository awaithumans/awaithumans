"use client";

import { ExternalLink, Slack, Trash2 } from "lucide-react";
import { useCallback, useEffect, useState } from "react";

import { TerminalSpinner } from "@/components/terminal-spinner";
import {
	fetchSlackInstallations,
	fetchSystemStatus,
	uninstallSlackWorkspace,
	type SlackInstallation,
	type SystemStatus,
} from "@/lib/server";
import { formatRelativeTime } from "@/lib/utils";
import { SettingsSection } from "./section";

export function SlackWorkspaces() {
	const [installs, setInstalls] = useState<SlackInstallation[] | null>(null);
	const [slackMode, setSlackMode] = useState<SystemStatus["slack_mode"] | null>(
		null,
	);
	const [error, setError] = useState<string | null>(null);
	const [deletingId, setDeletingId] = useState<string | null>(null);

	const load = useCallback(async () => {
		try {
			const [list, status] = await Promise.all([
				fetchSlackInstallations(),
				fetchSystemStatus(),
			]);
			setInstalls(list);
			setSlackMode(status.slack_mode);
			setError(null);
		} catch (err) {
			setError(err instanceof Error ? err.message : "Failed to load");
		}
	}, []);

	useEffect(() => {
		load();
	}, [load]);

	const handleUninstall = async (teamId: string) => {
		if (!confirm(`Uninstall workspace ${teamId}?`)) return;
		setDeletingId(teamId);
		try {
			await uninstallSlackWorkspace(teamId);
			await load();
		} catch (err) {
			setError(err instanceof Error ? err.message : "Uninstall failed");
		} finally {
			setDeletingId(null);
		}
	};

	const canInstall = slackMode === "multi-workspace";

	return (
		<SettingsSection
			icon={Slack}
			title="Slack workspaces"
			description={
				canInstall
					? "Workspaces that have granted this server a bot token. Uninstall to revoke."
					: "Multi-workspace OAuth isn't configured. Set SLACK_CLIENT_ID + SLACK_CLIENT_SECRET + SLACK_INSTALL_TOKEN to let teams install from the browser."
			}
			action={
				canInstall ? (
					<InstallButton />
				) : slackMode === "single-workspace" ? (
					<span className="text-xs text-white/40 px-3 py-1.5 border border-white/10 rounded-md">
						Static bot token mode
					</span>
				) : null
			}
		>
			{/* error is terminal — the banner above already renders it.
			    When installs is null without an error, we're still fetching. */}
			{error ? (
				<div className="px-5 py-4 text-red-400 text-xs">{error}</div>
			) : installs === null ? (
				<div className="px-5 py-4">
					<TerminalSpinner label="listing workspaces" />
				</div>
			) : installs.length === 0 ? (
				<div className="px-5 py-6 text-center text-white/35 text-sm">
					No workspaces yet.
				</div>
			) : (
				<ul className="divide-y divide-white/5">
					{installs.map((i) => (
						<li
							key={i.team_id}
							className="px-5 py-3 flex items-center justify-between gap-4"
						>
							<div className="min-w-0">
								<div className="text-sm font-medium truncate">
									{i.team_name || i.team_id}
								</div>
								<div className="text-white/35 text-xs font-mono truncate">
									{i.team_id} · {i.scopes.split(",").length} scopes · installed{" "}
									{formatRelativeTime(i.installed_at)}
								</div>
							</div>
							<button
								type="button"
								onClick={() => handleUninstall(i.team_id)}
								disabled={deletingId === i.team_id}
								className="flex items-center gap-1.5 text-xs text-red-400/80 hover:text-red-400 disabled:opacity-40 transition-colors px-2 py-1 rounded-md hover:bg-red-400/5"
							>
								<Trash2 size={13} />
								{deletingId === i.team_id ? "Removing…" : "Uninstall"}
							</button>
						</li>
					))}
				</ul>
			)}
		</SettingsSection>
	);
}

function InstallButton() {
	// The install endpoint requires ?install_token=X. We don't know the
	// token (server-side secret), so we link the operator to a page
	// they can paste the token into — or, more typically, they hit
	// /api/channels/slack/oauth/start?install_token=… themselves from
	// the terminal that sourced the env. The button here is a
	// documentation affordance, not a direct deep link.
	return (
		<a
			href="/api/channels/slack/oauth/start"
			target="_blank"
			rel="noopener noreferrer"
			className="inline-flex items-center gap-1.5 px-3 py-1.5 border border-brand/30 text-brand hover:bg-brand/5 rounded-md text-xs font-medium transition-colors"
		>
			<ExternalLink size={13} />
			Install workspace
		</a>
	);
}
