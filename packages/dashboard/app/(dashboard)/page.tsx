"use client";

import { ChevronRight, Inbox } from "lucide-react";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { EmptyState } from "@/components/empty-state";
import { ErrorBanner } from "@/components/error-banner";
import { TableSkeleton } from "@/components/skeleton";
import { StatusBadge } from "@/components/status-badge";
import {
	SECONDS_PER_MINUTE,
	TASK_ID_TRUNCATE_LENGTH,
	TASK_LIST_POLL_INTERVAL_MS,
} from "@/lib/constants";
import { fetchTasks, type Task, type TaskStatus } from "@/lib/server";
import { cn, formatRelativeTime } from "@/lib/utils";

const STATUS_FILTERS: { label: string; value: TaskStatus | "all" }[] = [
	{ label: "All", value: "all" },
	{ label: "Pending", value: "created" },
	{ label: "Assigned", value: "assigned" },
	{ label: "Completed", value: "completed" },
	{ label: "Timed out", value: "timed_out" },
	{ label: "Cancelled", value: "cancelled" },
];

// Statuses that count as "still waiting on a human" — drives the
// brand-tinted leading dot on the task row.
const ACTIVE_STATUSES: TaskStatus[] = [
	"created",
	"notified",
	"assigned",
	"in_progress",
	"submitted",
];

export default function TaskQueuePage() {
	const router = useRouter();
	const [tasks, setTasks] = useState<Task[]>([]);
	const [loading, setLoading] = useState(true);
	const [error, setError] = useState<string | null>(null);
	const [statusFilter, setStatusFilter] = useState<TaskStatus | "all">("all");

	const loadTasks = async () => {
		try {
			setError(null);
			const params = statusFilter === "all" ? {} : { status: statusFilter };
			const data = await fetchTasks(params);
			setTasks(data);
		} catch (err) {
			setError(err instanceof Error ? err.message : "Failed to load tasks");
		} finally {
			setLoading(false);
		}
	};

	useEffect(() => {
		loadTasks();
		const interval = setInterval(loadTasks, TASK_LIST_POLL_INTERVAL_MS);
		return () => clearInterval(interval);
		// eslint-disable-next-line react-hooks/exhaustive-deps
	}, [statusFilter]);

	return (
		<div>
			<header className="mb-6">
				<div className="flex items-end justify-between gap-4 mb-4">
					<div>
						<h1 className="text-[28px] font-semibold tracking-tight leading-none">
							Tasks
						</h1>
						<p className="text-white/45 text-sm mt-2">
							{loading
								? "Loading…"
								: `${tasks.length} task${tasks.length === 1 ? "" : "s"}${
										statusFilter !== "all" ? ` · filtered` : ""
									}`}
						</p>
					</div>
				</div>

				<div className="inline-flex border border-white/[0.07] rounded-md overflow-hidden">
					{STATUS_FILTERS.map((f, i) => (
						<button
							key={f.value}
							type="button"
							onClick={() => setStatusFilter(f.value)}
							className={cn(
								"px-3.5 py-1.5 text-xs font-medium transition-colors border-l border-white/[0.05] first:border-l-0",
								statusFilter === f.value
									? "bg-white/[0.06] text-fg"
									: "text-white/50 hover:text-white hover:bg-white/[0.02]",
							)}
						>
							{f.label}
						</button>
					))}
				</div>
			</header>

			{error && <ErrorBanner message={error} />}

			{loading ? (
				<div className="border border-white/[0.07] rounded-lg overflow-hidden">
					<TableSkeleton />
				</div>
			) : tasks.length === 0 ? (
				<div className="border border-white/[0.07] rounded-lg">
					<EmptyState
						icon={Inbox}
						title="No tasks yet"
						description={
							statusFilter === "all"
								? "Tasks will appear here when an agent calls await_human()."
								: "No tasks match this filter. Try a different status."
						}
					/>
				</div>
			) : (
				<div className="border border-white/[0.07] rounded-lg overflow-hidden">
					<table className="w-full">
						<thead>
							<tr className="border-b border-white/[0.07] text-left text-white/40 text-[10px] uppercase tracking-[0.08em] font-medium bg-white/[0.015]">
								<th className="pl-5 pr-4 py-2.5">Task</th>
								<th className="px-4 py-2.5">Status</th>
								<th className="px-4 py-2.5">Assigned to</th>
								<th className="px-4 py-2.5">Created</th>
								<th className="px-4 py-2.5 pr-5 text-right">Timeout</th>
							</tr>
						</thead>
						<tbody>
							{tasks.map((task) => {
								const isActive = ACTIVE_STATUSES.includes(task.status);
								return (
									<tr
										key={task.id}
										tabIndex={0}
										onClick={() => router.push(`/tasks/${task.id}`)}
										onKeyDown={(e) => {
											if (e.key === "Enter") router.push(`/tasks/${task.id}`);
										}}
										className="group border-b border-white/[0.04] last:border-b-0 hover:bg-white/[0.02] transition-colors cursor-pointer focus:outline-none focus:bg-white/[0.03]"
									>
										<td className="pl-5 pr-4 py-3.5 relative">
											<div className="flex items-start gap-3">
												<span
													className={cn(
														"mt-1.5 inline-block w-1.5 h-1.5 rounded-full shrink-0",
														isActive
															? "bg-brand shadow-[0_0_6px_rgba(0,230,118,0.6)]"
															: "bg-white/15",
													)}
													aria-hidden
												/>
												<div className="min-w-0">
													<div className="font-medium text-sm text-fg truncate">
														{task.task}
													</div>
													<div className="text-white/30 text-[11px] font-mono mt-0.5">
														{task.id.slice(0, TASK_ID_TRUNCATE_LENGTH)}…
													</div>
												</div>
											</div>
										</td>
										<td className="px-4 py-3.5">
											<StatusBadge status={task.status} />
										</td>
										<td className="px-4 py-3.5 text-sm text-white/55">
											{task.assigned_to_email ?? (task.assign_to ? "Routed" : "—")}
										</td>
										<td className="px-4 py-3.5 text-sm text-white/45 tabular-nums">
											{formatRelativeTime(task.created_at)}
										</td>
										<td className="px-4 py-3.5 pr-5 text-right">
											<div className="inline-flex items-center gap-1 text-sm text-white/45 tabular-nums">
												{Math.round(task.timeout_seconds / SECONDS_PER_MINUTE)}m
												<ChevronRight
													size={14}
													className="text-white/20 group-hover:text-white/40 transition-colors"
												/>
											</div>
										</td>
									</tr>
								);
							})}
						</tbody>
					</table>
				</div>
			)}
		</div>
	);
}
