"use client";

import { AlertTriangle, Mail, MessageSquare } from "lucide-react";
import type { AuditEntry } from "@/lib/server";

/*
 * Surfaces `notification_failed` audit entries for a single task.
 *
 * Rendered at the top of the task detail page when notify() couldn't
 * reach one or more recipients. Notify is best-effort background work
 * and we deliberately don't roll back task creation on a delivery
 * failure — but without this banner the operator only finds out by
 * reading the server log (often not accessible on managed deploys)
 * or by waiting for a human who never got pinged.
 *
 * Only renders when the audit trail contains at least one
 * `notification_failed` entry. List/index pages don't use this; this
 * is task-detail only.
 */
export function NotificationFailureBanner({ audit }: { audit: AuditEntry[] }) {
	const failures = audit.filter((e) => e.action === "notification_failed");
	if (failures.length === 0) return null;

	return (
		<div className="bg-amber-500/10 border border-amber-500/30 rounded-lg p-4 mb-4">
			<div className="flex items-center gap-2 text-amber-400 text-sm font-semibold mb-2">
				<AlertTriangle className="w-4 h-4" />
				{failures.length === 1
					? "Notification could not be delivered"
					: `${failures.length} notifications could not be delivered`}
			</div>
			<ul className="space-y-2">
				{failures.map((f) => (
					<NotificationFailureRow key={f.id} entry={f} />
				))}
			</ul>
		</div>
	);
}

function NotificationFailureRow({ entry }: { entry: AuditEntry }) {
	const data = entry.extra_data ?? {};
	const recipient = typeof data.recipient === "string" ? data.recipient : "—";
	const message = typeof data.message === "string" ? data.message : undefined;
	const reason = typeof data.reason === "string" ? data.reason : undefined;

	const Icon =
		entry.channel === "email"
			? Mail
			: entry.channel === "slack"
				? MessageSquare
				: AlertTriangle;

	return (
		<li className="flex items-start gap-2 text-sm">
			<Icon className="w-4 h-4 text-amber-400/80 mt-0.5 flex-shrink-0" />
			<div className="flex-1 min-w-0">
				<div className="text-white/90">
					<span className="font-medium">{entry.channel ?? "channel"}</span>
					{" → "}
					<span className="font-mono text-white/70">{recipient}</span>
					{reason && (
						<span className="ml-2 text-white/40 text-xs">({reason})</span>
					)}
				</div>
				{message && (
					<div className="text-white/50 text-xs mt-0.5">{message}</div>
				)}
			</div>
		</li>
	);
}
