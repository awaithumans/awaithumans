"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import {
	fetchTask,
	fetchAuditTrail,
	completeTask,
	cancelTask,
	type Task,
	type AuditEntry,
} from "@/lib/api";
import { cn, formatRelativeTime, statusBadgeColor } from "@/lib/utils";

export default function TaskDetailPage() {
	const params = useParams();
	const router = useRouter();
	const taskId = params.id as string;

	const [task, setTask] = useState<Task | null>(null);
	const [audit, setAudit] = useState<AuditEntry[]>([]);
	const [loading, setLoading] = useState(true);
	const [error, setError] = useState<string | null>(null);
	const [submitting, setSubmitting] = useState(false);
	const [formData, setFormData] = useState<Record<string, unknown>>({});

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

			// Initialize form data from response schema
			if (taskData.response_schema?.properties) {
				const initial: Record<string, unknown> = {};
				for (const [key, schema] of Object.entries(
					taskData.response_schema.properties as Record<string, Record<string, unknown>>,
				)) {
					if (schema.type === "boolean") initial[key] = false;
					else if (schema.type === "string") initial[key] = "";
					else if (schema.type === "number" || schema.type === "integer") initial[key] = 0;
					else initial[key] = null;
				}
				setFormData(initial);
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
		? ["completed", "timed_out", "cancelled", "verification_exhausted"].includes(task.status)
		: false;

	if (loading) {
		return <div className="text-white/40 text-sm">Loading task...</div>;
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
						<span
							className={cn(
								"inline-flex px-2 py-0.5 text-xs rounded-full border",
								statusBadgeColor(task.status),
							)}
						>
							{task.status}
						</span>
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

			{error && (
				<div className="bg-red-500/10 border border-red-500/20 rounded-lg p-4 mb-6 text-red-400 text-sm">
					{error}
				</div>
			)}

			<div className="grid grid-cols-3 gap-6">
				{/* Left: Payload + Response Form */}
				<div className="col-span-2 space-y-6">
					{/* Payload */}
					<div className="border border-white/10 rounded-lg p-5">
						<h2 className="text-sm font-semibold text-white/60 uppercase tracking-wider mb-4">
							Task Payload
						</h2>
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
													className="text-[#00E676] hover:underline"
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
					{!isTerminal && task.response_schema?.properties && (
						<div className="border border-[#00E676]/20 rounded-lg p-5 bg-[#00E676]/5">
							<h2 className="text-sm font-semibold text-[#00E676] uppercase tracking-wider mb-4">
								Your Response
							</h2>
							<div className="space-y-4">
								{Object.entries(
									task.response_schema.properties as Record<
										string,
										Record<string, unknown>
									>,
								).map(([key, schema]) => (
									<div key={key}>
										<label
											htmlFor={key}
											className="block text-sm text-white/60 mb-1.5"
										>
											{(schema.description as string) || key}
										</label>
										{schema.type === "boolean" ? (
											<div className="flex gap-3">
												<button
													type="button"
													onClick={() =>
														setFormData((prev) => ({ ...prev, [key]: true }))
													}
													className={cn(
														"px-4 py-2 text-sm rounded-md border transition-colors",
														formData[key] === true
															? "bg-[#00E676]/20 text-[#00E676] border-[#00E676]/40"
															: "bg-white/5 text-white/50 border-white/10 hover:text-white",
													)}
												>
													Yes
												</button>
												<button
													type="button"
													onClick={() =>
														setFormData((prev) => ({ ...prev, [key]: false }))
													}
													className={cn(
														"px-4 py-2 text-sm rounded-md border transition-colors",
														formData[key] === false
															? "bg-red-400/20 text-red-400 border-red-400/40"
															: "bg-white/5 text-white/50 border-white/10 hover:text-white",
													)}
												>
													No
												</button>
											</div>
										) : schema.enum ? (
											<select
												id={key}
												value={String(formData[key] ?? "")}
												onChange={(e) =>
													setFormData((prev) => ({
														...prev,
														[key]: e.target.value,
													}))
												}
												className="w-full bg-white/5 border border-white/10 rounded-md px-3 py-2 text-sm text-white focus:outline-none focus:border-[#00E676]/40"
											>
												<option value="">Select...</option>
												{(schema.enum as string[]).map((opt) => (
													<option key={opt} value={opt}>
														{opt}
													</option>
												))}
											</select>
										) : schema.type === "number" || schema.type === "integer" ? (
											<input
												id={key}
												type="number"
												value={String(formData[key] ?? "")}
												onChange={(e) =>
													setFormData((prev) => ({
														...prev,
														[key]: Number(e.target.value),
													}))
												}
												className="w-full bg-white/5 border border-white/10 rounded-md px-3 py-2 text-sm text-white focus:outline-none focus:border-[#00E676]/40"
											/>
										) : (
											<input
												id={key}
												type="text"
												value={String(formData[key] ?? "")}
												onChange={(e) =>
													setFormData((prev) => ({
														...prev,
														[key]: e.target.value || null,
													}))
												}
												placeholder={
													(schema.description as string) || `Enter ${key}`
												}
												className="w-full bg-white/5 border border-white/10 rounded-md px-3 py-2 text-sm text-white placeholder:text-white/20 focus:outline-none focus:border-[#00E676]/40"
											/>
										)}
									</div>
								))}

								<button
									type="button"
									onClick={handleSubmit}
									disabled={submitting}
									className="mt-4 px-6 py-2.5 bg-[#00E676] text-black font-semibold text-sm rounded-md hover:bg-[#00E676]/90 disabled:opacity-50 transition-colors"
								>
									{submitting ? "Submitting..." : "Submit Response"}
								</button>
							</div>
						</div>
					)}

					{/* Completed Response */}
					{task.response && (
						<div className="border border-white/10 rounded-lg p-5">
							<h2 className="text-sm font-semibold text-white/60 uppercase tracking-wider mb-4">
								Response
							</h2>
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
														value ? "text-[#00E676]" : "text-red-400"
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
					<h2 className="text-sm font-semibold text-white/60 uppercase tracking-wider mb-4">
						Timeline
					</h2>
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
													? "bg-[#00E676]/20 border-[#00E676]"
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
							{Math.round(task.timeout_seconds / 60)} minutes
						</div>
						<div>
							<span className="text-white/50">Created:</span>{" "}
							{new Date(task.created_at).toLocaleString()}
						</div>
						<div>
							<span className="text-white/50">Idempotency:</span>{" "}
							<span className="font-mono">{task.idempotency_key.slice(0, 16)}...</span>
						</div>
					</div>
				</div>
			</div>
		</div>
	);
}
