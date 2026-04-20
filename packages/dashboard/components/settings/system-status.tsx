"use client";

import { Server } from "lucide-react";
import { useEffect, useState } from "react";

import { Eyebrow } from "@/components/eyebrow";
import { TerminalSpinner } from "@/components/terminal-spinner";
import { fetchSystemStatus, type SystemStatus } from "@/lib/server";
import { SettingsSection, StatusDot } from "./section";

export function SystemStatusCard() {
	const [status, setStatus] = useState<SystemStatus | null>(null);
	const [error, setError] = useState<string | null>(null);

	useEffect(() => {
		fetchSystemStatus()
			.then(setStatus)
			.catch((err) =>
				setError(err instanceof Error ? err.message : "Failed to load status"),
			);
	}, []);

	return (
		<SettingsSection
			icon={Server}
			title="System"
			description="Snapshot of how the server is configured. No secrets — just what's on and what's off."
			flat
		>
			{error ? (
				<div className="pt-2 text-red-400 text-xs">{error}</div>
			) : !status ? (
				<div className="pt-2">
					<TerminalSpinner label="probing server" />
				</div>
			) : (
				// Flat list — no outer card. Each row is its own line in a
				// config file: label on the left, value on the right,
				// divided by a hairline.
				<dl className="divide-y divide-white/5 border-y border-white/5">
					<Row label="Version" value={status.version} />
					<Row
						label="Environment"
						value={status.environment}
					/>
					<Row
						label="Public URL"
						value={<code className="text-xs">{status.public_url}</code>}
					/>
					<Row
						label="Dashboard auth"
						value={
							<ModeBadge
								on={status.auth_enabled}
								onText="Password enabled"
								offText="No password (proxy mode)"
							/>
						}
					/>
					<Row
						label="Payload encryption"
						value={
							<ModeBadge
								on={status.payload_encryption_enabled}
								onText="PAYLOAD_KEY configured"
								offText="Not configured"
								warnWhenOff
							/>
						}
					/>
					<Row
						label="Admin API token"
						value={
							<ModeBadge
								on={status.admin_token_enabled}
								onText="Configured"
								offText="Not configured"
							/>
						}
					/>
					<Row
						label="Slack"
						value={<SlackBadge mode={status.slack_mode} />}
					/>
					<Row
						label="Email transport"
						value={
							status.email_transport ? (
								<span className="text-brand">
									{status.email_transport}
									{status.email_from ? (
										<span className="text-muted">
											{" "}· {status.email_from}
										</span>
									) : null}
								</span>
							) : (
								<ModeBadge on={false} onText="" offText="Not configured" />
							)
						}
					/>
				</dl>
			)}
		</SettingsSection>
	);
}

function Row({
	label,
	value,
}: {
	label: string;
	value: React.ReactNode;
}) {
	return (
		<div className="flex items-center justify-between gap-4 py-3 text-sm">
			<Eyebrow as="dt">{label}</Eyebrow>
			<dd className="text-right">{value}</dd>
		</div>
	);
}

function ModeBadge({
	on,
	onText,
	offText,
	warnWhenOff,
}: {
	on: boolean;
	onText: string;
	offText: string;
	warnWhenOff?: boolean;
}) {
	const state = on ? "ok" : warnWhenOff ? "warn" : "off";
	return (
		<span className="inline-flex items-center gap-2 text-xs">
			<StatusDot state={state} />
			<span className={on ? "text-fg" : "text-muted"}>
				{on ? onText : offText}
			</span>
		</span>
	);
}

function SlackBadge({ mode }: { mode: string }) {
	if (mode === "off") {
		return <ModeBadge on={false} onText="" offText="Not configured" />;
	}
	const label =
		mode === "single-workspace"
			? "Single workspace (static bot token)"
			: "Multi-workspace (OAuth)";
	return (
		<span className="inline-flex items-center gap-2 text-xs">
			<StatusDot state="ok" />
			<span>{label}</span>
		</span>
	);
}
