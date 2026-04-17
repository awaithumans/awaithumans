import { cn } from "@/lib/utils";

/**
 * Shimmering rectangle placeholder — fills the space a loaded
 * component will occupy, so layout doesn't jump when data arrives.
 */
export function Skeleton({ className }: { className?: string }) {
	return (
		<div
			className={cn(
				"bg-white/5 rounded animate-pulse",
				className,
			)}
			aria-hidden
		/>
	);
}

/** Preset row for table-style loading lists. */
export function TableSkeleton({ rows = 6 }: { rows?: number }) {
	return (
		<div className="space-y-px" aria-hidden>
			{Array.from({ length: rows }).map((_, i) => (
				<div
					key={i}
					className="grid grid-cols-[2fr_1fr_1fr_1fr_1fr] gap-4 px-4 py-3 border-b border-white/[0.04]"
				>
					<Skeleton className="h-4 w-3/4" />
					<Skeleton className="h-4 w-16" />
					<Skeleton className="h-4 w-24" />
					<Skeleton className="h-4 w-20" />
					<Skeleton className="h-4 w-12" />
				</div>
			))}
		</div>
	);
}
