import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
	return twMerge(clsx(inputs));
}

/**
 * Short relative-time formatter for task timestamps.
 *
 * Returns "just now" for anything < 10 seconds or future-dated. Future
 * dates happen when the dashboard's clock trails the server's (or when
 * we seed demo data with `now()` values that arrive before the dashboard
 * renders) — showing "-19579s ago" is worse than a tiny lie.
 */
export function formatRelativeTime(dateString: string): string {
	const date = new Date(dateString);
	const diffMs = Date.now() - date.getTime();
	const diffSeconds = Math.floor(diffMs / 1000);

	if (diffSeconds < 10) return "just now";

	const diffMinutes = Math.floor(diffSeconds / 60);
	const diffHours = Math.floor(diffMinutes / 60);
	const diffDays = Math.floor(diffHours / 24);

	if (diffSeconds < 60) return `${diffSeconds}s ago`;
	if (diffMinutes < 60) return `${diffMinutes}m ago`;
	if (diffHours < 24) return `${diffHours}h ago`;
	if (diffDays < 30) return `${diffDays}d ago`;

	const diffMonths = Math.floor(diffDays / 30);
	if (diffMonths < 12) return `${diffMonths}mo ago`;
	return `${Math.floor(diffMonths / 12)}y ago`;
}

/**
 * Humanize a task status value for display: "timed_out" → "Timed out".
 */
export function formatStatus(status: string): string {
	return status
		.split("_")
		.map((word, i) => (i === 0 ? word[0].toUpperCase() + word.slice(1) : word))
		.join(" ");
}

export function statusBadgeColor(status: string): string {
	switch (status) {
		case "completed":
			return "bg-brand/10 text-brand border-brand/20";
		case "timed_out":
		case "cancelled":
		case "verification_exhausted":
		case "rejected":
			return "bg-red-400/10 text-red-400 border-red-400/20";
		case "created":
		case "notified":
			return "bg-yellow-400/10 text-yellow-400 border-yellow-400/20";
		case "assigned":
		case "in_progress":
		case "submitted":
		case "verified":
			return "bg-blue-400/10 text-blue-400 border-blue-400/20";
		default:
			return "bg-white/10 text-white/70 border-white/20";
	}
}
