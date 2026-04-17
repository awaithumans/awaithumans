import type { LucideIcon } from "lucide-react";

import { cn } from "@/lib/utils";

/**
 * Single-metric card — big number + label + optional sub-line.
 *
 * `accent` swaps the value colour to brand-green; reserve it for the
 * headline KPI so the eye reads that card first.
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
				"border border-white/[0.07] rounded-lg px-5 py-4 bg-white/[0.015] transition-colors hover:bg-white/[0.025]",
				className,
			)}
		>
			<div className="flex items-center gap-1.5 text-white/45 text-[10px] uppercase tracking-[0.08em] font-medium">
				{Icon && <Icon size={12} strokeWidth={2} />}
				<span>{label}</span>
			</div>
			<div
				className={cn(
					"mt-2 text-[28px] leading-none font-semibold tabular-nums tracking-tight",
					accent ? "text-brand" : "text-fg",
				)}
			>
				{value}
			</div>
			{sub && (
				<div className="mt-1.5 text-white/40 text-xs tabular-nums">{sub}</div>
			)}
		</div>
	);
}
