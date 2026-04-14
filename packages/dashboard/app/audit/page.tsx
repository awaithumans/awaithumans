"use client";

import { useEffect, useState } from "react";
import { fetchTasks, type Task } from "@/lib/api";
import { cn, formatRelativeTime, statusBadgeColor } from "@/lib/utils";

export default function AuditLogPage() {
	const [tasks, setTasks] = useState<Task[]>([]);
	const [loading, setLoading] = useState(true);

	useEffect(() => {
		fetchTasks({ limit: 100 })
			.then(setTasks)
			.finally(() => setLoading(false));
	}, []);

	const completedTasks = tasks.filter(
		(t) => t.status === "completed" || t.status === "timed_out" || t.status === "cancelled",
	);

	return (
		<div>
			<div className="mb-6">
				<h1 className="text-2xl font-bold">Audit Log</h1>
				<p className="text-white/40 text-sm mt-1">
					Who approved what, when, and how.
				</p>
			</div>

			{loading ? (
				<div className="text-white/40 text-sm">Loading...</div>
			) : completedTasks.length === 0 ? (
				<div className="text-center py-20">
					<p className="text-white/40 text-lg">No completed tasks yet</p>
					<p className="text-white/20 text-sm mt-2">
						Audit entries will appear here after tasks are completed.
					</p>
				</div>
			) : (
				<div className="border border-white/10 rounded-lg overflow-hidden">
					<table className="w-full">
						<thead>
							<tr className="border-b border-white/10 text-left text-white/40 text-xs uppercase tracking-wider">
								<th className="px-4 py-3">Task</th>
								<th className="px-4 py-3">Status</th>
								<th className="px-4 py-3">Completed By</th>
								<th className="px-4 py-3">Channel</th>
								<th className="px-4 py-3">Completed At</th>
								<th className="px-4 py-3">Duration</th>
							</tr>
						</thead>
						<tbody>
							{completedTasks.map((task) => {
								const createdAt = new Date(task.created_at).getTime();
								const endedAt = task.completed_at
									? new Date(task.completed_at).getTime()
									: task.timed_out_at
										? new Date(task.timed_out_at).getTime()
										: Date.now();
								const durationMs = endedAt - createdAt;
								const durationMin = Math.round(durationMs / 60000);

								return (
									<tr
										key={task.id}
										className="border-b border-white/5 hover:bg-white/5 transition-colors cursor-pointer"
										onClick={() => {
											window.location.href = `/tasks/${task.id}`;
										}}
									>
										<td className="px-4 py-3">
											<div className="text-sm font-medium">{task.task}</div>
											<div className="text-white/30 text-xs font-mono mt-0.5">
												{task.id.slice(0, 12)}...
											</div>
										</td>
										<td className="px-4 py-3">
											<span
												className={cn(
													"inline-flex px-2 py-0.5 text-xs rounded-full border",
													statusBadgeColor(task.status),
												)}
											>
												{task.status}
											</span>
										</td>
										<td className="px-4 py-3 text-sm text-white/60">
											{task.completed_by_email ?? "—"}
										</td>
										<td className="px-4 py-3 text-sm text-white/40">
											{task.completed_via_channel ?? "—"}
										</td>
										<td className="px-4 py-3 text-sm text-white/40">
											{task.completed_at
												? formatRelativeTime(task.completed_at)
												: task.timed_out_at
													? formatRelativeTime(task.timed_out_at)
													: "—"}
										</td>
										<td className="px-4 py-3 text-sm text-white/40">
											{durationMin < 1 ? "<1m" : `${durationMin}m`}
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
