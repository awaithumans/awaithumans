import type { LucideIcon } from "lucide-react";

import { cn } from "@/lib/utils";

/**
 * Single-metric card — big number + label + optional delta/sub-line.
 *
 * `accent` swaps the number colour; we reserve brand-green for the
 * completion-rate card so the main KPI reads first.
 */
export function StatCard({
	icon: Icon,
	label,
	value,
	sub,
	accent,
	className,
}: {
	icon?: LucideIcon;
	label: string;
	value: React.ReactNode;
	sub?: React.ReactNode;
	accent?: boolean;
	className?: string;
}) {
	return (
		<div
			className={cn(
				"border border-white/10 rounded-lg px-5 py-4 bg-white/[0.015]",
				className,
			)}
		>
			<div className="flex items-center gap-2 text-white/40 text-[10px] uppercase tracking-wider font-medium">
				{Icon && <Icon size={12} />}
				<span>{label}</span>
			</div>
			<div
				className={cn(
					"mt-1.5 text-2xl font-semibold tabular-nums",
					accent ? "text-brand" : "text-fg",
				)}
			>
				{value}
			</div>
			{sub && (
				<div className="mt-1 text-white/40 text-xs tabular-nums">{sub}</div>
			)}
		</div>
	);
}
