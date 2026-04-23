"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { fetchTasks, type Task, type TaskStatus } from "@/lib/server";
import { cn, formatRelativeTime } from "@/lib/utils";
import {
	SECONDS_PER_MINUTE,
	TASK_ID_TRUNCATE_LENGTH,
	TASK_LIST_POLL_INTERVAL_MS,
} from "@/lib/constants";
import { ErrorBanner } from "@/components/error-banner";
import { ShellEmptyState } from "@/components/shell-empty-state";
import { StatusBadge } from "@/components/status-badge";
import { TerminalSpinner } from "@/components/terminal-spinner";

const STATUS_FILTERS: { label: string; value: TaskStatus | "all" }[] = [
	{ label: "All", value: "all" },
	{ label: "Pending", value: "created" },
	{ label: "Assigned", value: "assigned" },
	{ label: "Completed", value: "completed" },
	{ label: "Timed Out", value: "timed_out" },
	{ label: "Cancelled", value: "cancelled" },
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
		// Poll every 5 seconds for updates
		const interval = setInterval(loadTasks, TASK_LIST_POLL_INTERVAL_MS);
		return () => clearInterval(interval);
	}, [statusFilter]);

	return (
		<div>
			<div className="flex items-center justify-between mb-6">
				<div>
					<h1 className="text-2xl font-bold">Tasks</h1>
					<p className="text-white/40 text-sm mt-1">
						{tasks.length} task{tasks.length !== 1 ? "s" : ""}
					</p>
				</div>
				<div className="flex gap-2">
					{STATUS_FILTERS.map((f) => (
						<button
							key={f.value}
							type="button"
							onClick={() => setStatusFilter(f.value)}
							className={cn(
								"px-3 py-1.5 text-sm rounded-md border transition-colors",
								statusFilter === f.value
									? "bg-brand/10 text-brand border-brand/30"
									: "bg-white/5 text-white/50 border-white/10 hover:text-white/80",
							)}
						>
							{f.label}
						</button>
					))}
				</div>
			</div>

			{error && <ErrorBanner message={error} />}

			{loading ? (
				<TerminalSpinner label="awaiting tasks" size="md" />
			) : tasks.length === 0 ? (
				<ShellEmptyState
					heading="await_human — waiting for your first task"
					note="Save as refund.py / refund.ts, run it. A task appears the moment await_human() is called."
					snippet={{
						python: `from awaithumans import await_human_sync
from pydantic import BaseModel

class WireTransfer(BaseModel):
    amount: float
    to: str

class Decision(BaseModel):
    approved: bool

result = await_human_sync(
    task="Approve this wire transfer",
    payload_schema=WireTransfer,
    payload=WireTransfer(amount=50_000, to="acme.inc"),
    response_schema=Decision,
    timeout_seconds=900,
)
print("approved" if result.approved else "rejected")`,
						typescript: `import { awaitHuman } from "awaithumans";
import { z } from "zod";

const WireTransfer = z.object({
  amount: z.number(),
  to: z.string(),
});

const Decision = z.object({
  approved: z.boolean(),
});

async function main() {
  const result = await awaitHuman({
    task: "Approve this wire transfer",
    payloadSchema: WireTransfer,
    payload: { amount: 50_000, to: "acme.inc" },
    responseSchema: Decision,
    timeoutMs: 900_000,
  });
  console.log(result.approved ? "approved" : "rejected");
}

main();`,
					}}
				/>
			) : (
				<div className="border border-white/10 rounded-lg overflow-hidden">
					<table className="w-full">
						<thead>
							<tr className="border-b border-white/10 text-left text-white/40 text-xs uppercase tracking-wider">
								<th className="px-4 py-3">Task</th>
								<th className="px-4 py-3">Status</th>
								<th className="px-4 py-3">Assigned To</th>
								<th className="px-4 py-3">Created</th>
								<th className="px-4 py-3">Timeout</th>
							</tr>
						</thead>
						<tbody>
							{tasks.map((task) => (
								<tr
									key={task.id}
									className="border-b border-white/5 hover:bg-white/5 transition-colors cursor-pointer"
									onClick={() => {
										router.push(`/task?id=${encodeURIComponent(task.id)}`);
									}}
								>
									<td className="px-4 py-3">
										<div className="font-medium text-sm">{task.task}</div>
										<div className="text-white/30 text-xs font-mono mt-0.5">
											{task.id.slice(0, TASK_ID_TRUNCATE_LENGTH)}...
										</div>
									</td>
									<td className="px-4 py-3">
										<StatusBadge status={task.status} />
									</td>
									<td className="px-4 py-3 text-sm text-white/60">
										{task.assigned_to_email ?? task.assign_to ? "Routed" : "—"}
									</td>
									<td className="px-4 py-3 text-sm text-white/40">
										{formatRelativeTime(task.created_at)}
									</td>
									<td className="px-4 py-3 text-sm text-white/40">
										{Math.round(task.timeout_seconds / SECONDS_PER_MINUTE)}m
									</td>
								</tr>
							))}
						</tbody>
					</table>
				</div>
			)}
		</div>
	);
}
