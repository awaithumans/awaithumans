import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
	return twMerge(clsx(inputs));
}

export function formatRelativeTime(dateString: string): string {
	const date = new Date(dateString);
	const now = new Date();
	const diffMs = now.getTime() - date.getTime();
	const diffSeconds = Math.floor(diffMs / 1000);
	const diffMinutes = Math.floor(diffSeconds / 60);
	const diffHours = Math.floor(diffMinutes / 60);
	const diffDays = Math.floor(diffHours / 24);

	if (diffSeconds < 60) return `${diffSeconds}s ago`;
	if (diffMinutes < 60) return `${diffMinutes}m ago`;
	if (diffHours < 24) return `${diffHours}h ago`;
	return `${diffDays}d ago`;
}

export function statusColor(status: string): string {
	switch (status) {
		case "completed":
			return "text-[#00E676]";
		case "timed_out":
		case "cancelled":
		case "verification_exhausted":
			return "text-red-400";
		case "created":
		case "notified":
			return "text-yellow-400";
		case "assigned":
		case "in_progress":
		case "submitted":
			return "text-blue-400";
		default:
			return "text-[#F5F5F5]";
	}
}

export function statusBadgeColor(status: string): string {
	switch (status) {
		case "completed":
			return "bg-[#00E676]/10 text-[#00E676] border-[#00E676]/20";
		case "timed_out":
		case "cancelled":
		case "verification_exhausted":
			return "bg-red-400/10 text-red-400 border-red-400/20";
		case "created":
		case "notified":
			return "bg-yellow-400/10 text-yellow-400 border-yellow-400/20";
		case "assigned":
		case "in_progress":
		case "submitted":
			return "bg-blue-400/10 text-blue-400 border-blue-400/20";
		default:
			return "bg-white/10 text-white/70 border-white/20";
	}
}
