import { Mail, Monitor, Slack } from "lucide-react";
import type { LucideIcon } from "lucide-react";

import { cn } from "@/lib/utils";

const CHANNEL_META: Record<
	string,
	{ icon: LucideIcon; label: string }
> = {
	dashboard: { icon: Monitor, label: "Dashboard" },
	slack: { icon: Slack, label: "Slack" },
	email: { icon: Mail, label: "Email" },
};

/**
 * Horizontal stacked bar of completion channels, followed by a per-
 * channel breakdown. The stacked bar gives an at-a-glance "where are
 * humans actually working" read; the list gives the raw counts.
 */
export function ChannelMix({ byChannel }: { byChannel: Record<string, number> }) {
	const entries = Object.entries(byChannel).sort(
		([, a], [, b]) => b - a,
	);
	const total = entries.reduce((acc, [, n]) => acc + n, 0);

	if (total === 0) {
		return (
			<div className="border border-white/10 rounded-lg px-5 py-6 bg-white/[0.015] text-center text-sm text-white/35">
				No completions in the window yet.
			</div>
		);
	}

	return (
		<div className="border border-white/10 rounded-lg p-5 bg-white/[0.015] space-y-4">
			<div className="flex rounded-full overflow-hidden h-2 bg-white/5">
				{entries.map(([channel, count], i) => {
					const pct = (count / total) * 100;
					return (
						<div
							key={channel}
							className={cn("h-full", barColor(i))}
							style={{ width: `${pct}%` }}
							title={`${channel}: ${count}`}
						/>
					);
				})}
			</div>

			<ul className="space-y-2">
				{entries.map(([channel, count], i) => {
					const meta = CHANNEL_META[channel] ?? {
						icon: Monitor,
						label: channel,
					};
					const Icon = meta.icon;
					const pct = ((count / total) * 100).toFixed(0);
					return (
						<li
							key={channel}
							className="flex items-center gap-3 text-sm"
						>
							<span
								className={cn(
									"inline-block w-2 h-2 rounded-sm shrink-0",
									barColor(i),
								)}
							/>
							<Icon size={14} className="text-white/50" />
							<span className="flex-1">{meta.label}</span>
							<span className="text-white/40 text-xs tabular-nums">
								{count} · {pct}%
							</span>
						</li>
					);
				})}
			</ul>
		</div>
	);
}

// First entry always brand-green (it's the most-used channel). Subsequent
// entries step down in saturation so the eye reads the primary first.
function barColor(index: number): string {
	switch (index) {
		case 0:
			return "bg-brand";
		case 1:
			return "bg-white/40";
		case 2:
			return "bg-white/20";
		default:
			return "bg-white/10";
	}
}
