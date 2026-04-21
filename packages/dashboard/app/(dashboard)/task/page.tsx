"use client";

import { Suspense, useEffect, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import {
	fetchTask,
	fetchAuditTrail,
	completeTask,
	cancelTask,
	type Task,
	type AuditEntry,
} from "@/lib/server";
import { cn, formatRelativeTime } from "@/lib/utils";
import {
	IDEMPOTENCY_KEY_DISPLAY_LENGTH,
	SECONDS_PER_MINUTE,
	TERMINAL_STATUSES,
} from "@/lib/constants";
import { ErrorBanner } from "@/components/error-banner";
import { Eyebrow } from "@/components/eyebrow";
import { StatusBadge } from "@/components/status-badge";
import { TerminalSpinner } from "@/components/terminal-spinner";
import {
	FormRenderer,
	initialValueFor,
	type FormValue,
} from "@/components/form-renderer";

/**
 * Route is query-param (`/task?id=...`) rather than dynamic segment
 * (`/tasks/[id]`) so the dashboard can build to a flat static export
 * and ship inside the Python wheel. Dynamic segments without known
 * params at build time are incompatible with output: "export".
 *
 * `useSearchParams` requires a Suspense boundary in static export.
 */
export default function TaskDetailPage() {
	return (
		<Suspense fallback={<TerminalSpinner label="awaiting task" size="md" />}>
			<TaskDetailPageInner />
		</Suspense>
	);
}

function TaskDetailPageInner() {
	const router = useRouter();
	const searchParams = useSearchParams();
	const taskId = searchParams.get("id") ?? "";

	const [task, setTask] = useState<Task | null>(null);
	const [audit, setAudit] = useState<AuditEntry[]>([]);
	const [loading, setLoading] = useState(true);
	const [error, setError] = useState<string | null>(null);
	const [submitting, setSubmitting] = useState(false);
	const [formData, setFormData] = useState<FormValue>({});

	useEffect(() => {
		loadTask();
	}, [taskId]);

	const loadTask = async () => {
		try {
			setError(null);
			const [taskData, auditData] = await Promise.all([
				fetchTask(taskId),
				fetchAuditTrail(taskId),
			]);
			setTask(taskData);
			setAudit(auditData);

			if (taskData.form_definition) {
				setFormData(initialValueFor(taskData.form_definition));
			}
		} catch (err) {
			setError(err instanceof Error ? err.message : "Failed to load task");
		} finally {
			setLoading(false);
		}
	};

	const handleSubmit = async () => {
		if (!task) return;
		setSubmitting(true);
		try {
			await completeTask(task.id, {
				response: formData,
				completed_via_channel: "dashboard",
			});
			await loadTask();
		} catch (err) {
			setError(err instanceof Error ? err.message : "Failed to submit");
		} finally {
			setSubmitting(false);
		}
	};

	const handleCancel = async () => {
		if (!task) return;
		try {
			await cancelTask(task.id);
			await loadTask();
		} catch (err) {
			setError(err instanceof Error ? err.message : "Failed to cancel");
		}
	};

	const isTerminal = task?.status
		? TERMINAL_STATUSES.includes(task.status)
		: false;

	if (loading) {
		return <TerminalSpinner label="awaiting task" size="md" />;
	}

	if (!task) {
		return <div className="text-red-400">Task not found</div>;
	}

	return (
		<div className="max-w-5xl mx-auto">
			{/* Header */}
			<div className="flex items-start justify-between mb-8">
				<div>
					<button
						type="button"
						onClick={() => router.push("/")}
						className="text-white/40 text-sm hover:text-white/60 transition-colors mb-2 block"
					>
						← Back to tasks
					</button>
					<h1 className="text-2xl font-bold">{task.task}</h1>
					<div className="flex items-center gap-3 mt-2">
						<StatusBadge status={task.status} />
						<span className="text-white/30 text-xs font-mono">{task.id}</span>
					</div>
				</div>
				{!isTerminal && (
					<button
						type="button"
						onClick={handleCancel}
						className="px-3 py-1.5 text-sm rounded-md border border-red-400/30 text-red-400 hover:bg-red-400/10 transition-colors"
					>
						Cancel Task
					</button>
				)}
			</div>

			{error && <ErrorBanner message={error} />}

			<div className="grid grid-cols-3 gap-6">
				{/* Left: Payload + Response Form */}
				<div className="col-span-2 space-y-6">
					{/* Payload */}
					<div className="border border-white/10 rounded-lg p-5">
						<Eyebrow as="h2" size="md" tone="bright" weight="semibold" className="block mb-4">
							Task Payload
						</Eyebrow>
						{task.payload && !task.redact_payload ? (
							<div className="space-y-3">
								{Object.entries(task.payload).map(([key, value]) => (
									<div key={key} className="flex items-start gap-3">
										<span className="text-white/40 text-sm min-w-[120px] font-mono">
											{key}
										</span>
										<span className="text-sm break-all">
											{typeof value === "string" && value.startsWith("http") ? (
												<a
													href={value}
													target="_blank"
													rel="noopener noreferrer"
													className="text-brand hover:underline"
												>
													{value}
												</a>
											) : (
												String(value)
											)}
										</span>
									</div>
								))}
							</div>
						) : task.redact_payload ? (
							<div className="text-white/30 text-sm italic">Payload redacted</div>
						) : (
							<div className="text-white/30 text-sm">No payload</div>
						)}
					</div>

					{/* Response Form (if not terminal) */}
					{!isTerminal && task.form_definition && (
						<div className="border border-brand/20 rounded-lg p-5 bg-brand/5">
							<Eyebrow as="h2" size="md" tone="brand" weight="semibold" className="block mb-4">
								Your Response
							</Eyebrow>
							<FormRenderer
								form={task.form_definition}
								value={formData}
								onChange={setFormData}
								disabled={submitting}
							/>
							<button
								type="button"
								onClick={handleSubmit}
								disabled={submitting}
								className="mt-6 px-6 py-2.5 bg-brand text-black font-semibold text-sm rounded-md hover:bg-brand/90 disabled:opacity-50 transition-colors"
							>
								{submitting ? "Submitting..." : "Submit Response"}
							</button>
						</div>
					)}

					{/* Completed Response */}
					{task.response && (
						<div className="border border-white/10 rounded-lg p-5">
							<Eyebrow as="h2" size="md" tone="bright" weight="semibold" className="block mb-4">
								Response
							</Eyebrow>
							<div className="space-y-3">
								{Object.entries(task.response).map(([key, value]) => (
									<div key={key} className="flex items-start gap-3">
										<span className="text-white/40 text-sm min-w-[120px] font-mono">
											{key}
										</span>
										<span className="text-sm">
											{typeof value === "boolean" ? (
												<span
													className={
														value ? "text-brand" : "text-red-400"
													}
												>
													{value ? "Yes" : "No"}
												</span>
											) : (
												String(value)
											)}
										</span>
									</div>
								))}
							</div>
							{task.completed_by_email && (
								<div className="mt-4 text-white/30 text-xs">
									Completed by {task.completed_by_email} via{" "}
									{task.completed_via_channel ?? "unknown"}{" "}
									{task.completed_at && formatRelativeTime(task.completed_at)}
								</div>
							)}
						</div>
					)}
				</div>

				{/* Right: Timeline */}
				<div className="border border-white/10 rounded-lg p-5">
					<Eyebrow as="h2" size="md" tone="bright" weight="semibold" className="block mb-4">
						Timeline
					</Eyebrow>
					{audit.length === 0 ? (
						<div className="text-white/30 text-sm">No events yet</div>
					) : (
						<div className="space-y-4">
							{audit.map((entry, i) => (
								<div key={entry.id} className="relative">
									{i < audit.length - 1 && (
										<div className="absolute left-[7px] top-5 bottom-0 w-px bg-white/10" />
									)}
									<div className="flex items-start gap-3">
										<div
											className={cn(
												"w-[15px] h-[15px] rounded-full border-2 mt-0.5 flex-shrink-0",
												entry.to_status === "completed"
													? "bg-brand/20 border-brand"
													: entry.to_status === "timed_out" ||
														  entry.to_status === "cancelled"
														? "bg-red-400/20 border-red-400"
														: "bg-white/10 border-white/30",
											)}
										/>
										<div>
											<div className="text-sm font-medium">{entry.action}</div>
											<div className="text-white/30 text-xs mt-0.5">
												{entry.actor_type === "human" && entry.actor_email
													? entry.actor_email
													: entry.actor_type}
												{entry.channel && ` via ${entry.channel}`}
											</div>
											<div className="text-white/20 text-xs mt-0.5">
												{formatRelativeTime(entry.created_at)}
											</div>
										</div>
									</div>
								</div>
							))}
						</div>
					)}

					{/* Task metadata */}
					<div className="mt-6 pt-4 border-t border-white/10 space-y-2 text-xs text-white/30">
						<div>
							<span className="text-white/50">Timeout:</span>{" "}
							{Math.round(task.timeout_seconds / SECONDS_PER_MINUTE)} minutes
						</div>
						<div>
							<span className="text-white/50">Created:</span>{" "}
							{new Date(task.created_at).toLocaleString()}
						</div>
						<div>
							<span className="text-white/50">Idempotency:</span>{" "}
							<span className="font-mono">
								{task.idempotency_key.slice(0, IDEMPOTENCY_KEY_DISPLAY_LENGTH)}...
							</span>
						</div>
					</div>
				</div>
			</div>
		</div>
	);
}
