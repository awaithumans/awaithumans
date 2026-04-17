"use client";

import type { TaskStatus } from "@/lib/types";
import { cn, formatStatus, statusBadgeColor } from "@/lib/utils";

export function StatusBadge({
	status,
	size = "sm",
}: {
	status: TaskStatus;
	size?: "sm" | "xs";
}) {
	return (
		<span
			className={cn(
				"inline-flex items-center rounded-full border font-medium tracking-wide whitespace-nowrap",
				size === "xs"
					? "px-1.5 py-0.5 text-[10px]"
					: "px-2 py-0.5 text-xs",
				statusBadgeColor(status),
			)}
		>
			{formatStatus(status)}
		</span>
	);
}
