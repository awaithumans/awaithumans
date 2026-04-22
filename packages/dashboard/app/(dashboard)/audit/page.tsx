"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { fetchTasks, type Task } from "@/lib/server";
import { formatRelativeTime } from "@/lib/utils";
import { AUDIT_PAGE_DEFAULT_LIMIT, TASK_ID_TRUNCATE_LENGTH, TERMINAL_STATUSES } from "@/lib/constants";
import { ShellEmptyState } from "@/components/shell-empty-state";
import { StatusBadge } from "@/components/status-badge";
import { TerminalSpinner } from "@/components/terminal-spinner";

export default function AuditLogPage() {
	const router = useRouter();
	const [tasks, setTasks] = useState<Task[]>([]);
	const [loading, setLoading] = useState(true);

	useEffect(() => {
		fetchTasks({ limit: AUDIT_PAGE_DEFAULT_LIMIT })
			.then(setTasks)
			.finally(() => setLoading(false));
	}, []);

	const completedTasks = tasks.filter(
		(t) => TERMINAL_STATUSES.includes(t.status),
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
				<TerminalSpinner label="awaiting audit entries" size="md" />
			) : completedTasks.length === 0 ? (
				<ShellEmptyState
					heading="tail -f audit.log — no terminal events yet"
					note="Completed, timed-out, and cancelled tasks land here the moment they close."
				/>
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
											router.push(`/task?id=${encodeURIComponent(task.id)}`);
										}}
									>
										<td className="px-4 py-3">
											<div className="text-sm font-medium">{task.task}</div>
											<div className="text-white/30 text-xs font-mono mt-0.5">
												{task.id.slice(0, TASK_ID_TRUNCATE_LENGTH)}...
											</div>
										</td>
										<td className="px-4 py-3">
											<StatusBadge status={task.status} />
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
