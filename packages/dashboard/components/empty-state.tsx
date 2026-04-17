import type { LucideIcon } from "lucide-react";

import { cn } from "@/lib/utils";

/**
 * Shared empty-state — icon in a soft tile, heading, description, optional action.
 * Used whenever a list has zero items.
 */
export function EmptyState({
	icon: Icon,
	title,
	description,
	action,
	className,
}: {
	icon: LucideIcon;
	title: string;
	description?: string;
	action?: React.ReactNode;
	className?: string;
}) {
	return (
		<div
			className={cn(
				"flex flex-col items-center justify-center text-center py-16 px-6",
				className,
			)}
		>
			<div className="w-12 h-12 rounded-xl bg-white/[0.03] border border-white/[0.06] flex items-center justify-center text-white/40 mb-4">
				<Icon size={20} strokeWidth={1.75} />
			</div>
			<h3 className="text-sm font-semibold text-fg mb-1">{title}</h3>
			{description && (
				<p className="text-white/40 text-xs max-w-sm leading-relaxed">
					{description}
				</p>
			)}
			{action && <div className="mt-4">{action}</div>}
		</div>
	);
}
