"use client";

import type { TaskStatus } from "@/lib/types";
import { cn, statusBadgeColor } from "@/lib/utils";

export function StatusBadge({ status }: { status: TaskStatus }) {
	return (
		<span
			className={cn(
				"inline-flex px-2 py-0.5 text-xs rounded-full border",
				statusBadgeColor(status),
			)}
		>
			{status}
		</span>
	);
}
