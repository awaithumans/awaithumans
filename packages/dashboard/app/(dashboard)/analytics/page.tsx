import { BarChart3 } from "lucide-react";

import { ComingSoon } from "@/components/coming-soon";

export default function AnalyticsPage() {
	return (
		<ComingSoon
			icon={BarChart3}
			title="Analytics"
			body="Completion rate, time-to-complete, channel mix, and verifier outcomes across your tasks."
		/>
	);
}
