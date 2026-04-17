import { Settings as SettingsIcon } from "lucide-react";

import { ComingSoon } from "@/components/coming-soon";

export default function SettingsPage() {
	return (
		<ComingSoon
			icon={SettingsIcon}
			title="Settings"
			body="Slack workspaces, email sender identities, encryption key status, and the admin API token."
		/>
	);
}
