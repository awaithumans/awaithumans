import { EmailIdentities } from "@/components/settings/email-identities";
import { SlackWorkspaces } from "@/components/settings/slack-workspaces";
import { SystemStatusCard } from "@/components/settings/system-status";

export default function SettingsPage() {
	return (
		<div className="max-w-3xl">
			<div className="mb-8">
				<h1 className="text-2xl font-bold">Settings</h1>
				<p className="text-white/45 text-sm mt-1">
					Channel configuration and server state.
				</p>
			</div>

			<div className="space-y-10">
				<SystemStatusCard />
				<SlackWorkspaces />
				<EmailIdentities />
			</div>
		</div>
	);
}
