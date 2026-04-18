"use client";

import type { TaskStatus } from "@/lib/types";
import { cn, statusBadgeColor } from "@/lib/utils";

// Live states get a pulsing dot (the task is actively awaiting a human).
// Terminal states get a solid dot — the story is over.
const LIVE_STATUSES: ReadonlySet<TaskStatus> = new Set([
	"created",
	"notified",
	"assigned",
	"in_progress",
	"submitted",
	"verified",
]);

export function StatusBadge({ status }: { status: TaskStatus }) {
	const isLive = LIVE_STATUSES.has(status);
	return (
		<span
			className={cn(
				"inline-flex items-center gap-1.5 px-2 py-0.5 text-xs rounded-full border",
				statusBadgeColor(status),
			)}
		>
			<span
				className={cn(
					"w-1.5 h-1.5 rounded-full bg-current",
					isLive && "motion-safe:animate-pulse",
				)}
				aria-hidden
			/>
			{status}
		</span>
	);
}
