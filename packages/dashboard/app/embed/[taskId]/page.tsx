"use client";

import { useEffect, useRef, useState } from "react";

import { FormRenderer, initialValueFor, type FormValue } from "@/components/form-renderer";
import { EmbedFetchError, embedFetch } from "@/lib/embed/api";
import { postEmbed } from "@/lib/embed/post-message";
import { extractEmbedToken } from "@/lib/embed/token";
import type { CompleteTaskRequest, Task } from "@/lib/server";

export default function EmbedTaskPage({
	params,
}: {
	params: { taskId: string };
}) {
	const taskId = params.taskId;
	const [token, setToken] = useState<string | null>(null);
	const [task, setTask] = useState<Task | null>(null);
	const [value, setValue] = useState<FormValue>({});
	const [submitting, setSubmitting] = useState(false);
	const [error, setError] = useState<string | null>(null);
	const parentOriginRef = useRef<string>("");

	// 1. Extract token + parent_origin from URL fragment.
	useEffect(() => {
		const t = extractEmbedToken();
		if (!t) {
			setError("Missing embed token. The URL must include #token=...");
			postEmbed(parentOriginRef.current, {
				type: "task.error",
				payload: {
					taskId,
					code: "invalid_token",
					message: "Token missing from URL fragment",
				},
			});
			return;
		}
		setToken(t);
		try {
			const claims = JSON.parse(atob(t.split(".")[1])) as Record<string, unknown>;
			parentOriginRef.current =
				typeof claims.parent_origin === "string" ? claims.parent_origin : "";
		} catch {
			// best-effort decode; signature is verified server-side
		}
	}, [taskId]);

	// 2. Fetch task once token is available.
	useEffect(() => {
		if (!token) return;
		void (async () => {
			try {
				const fetched = await embedFetch<Task>(`/api/tasks/${taskId}`, {
					token,
					method: "GET",
				});
				setTask(fetched);
				if (fetched.form_definition) {
					setValue(initialValueFor(fetched.form_definition));
				}
				postEmbed(parentOriginRef.current, {
					type: "loaded",
					payload: { taskId },
				});
			} catch (e) {
				const code = e instanceof EmbedFetchError ? e.code : "internal";
				const message = e instanceof Error ? e.message : "Unknown error";
				setError(message);
				postEmbed(parentOriginRef.current, {
					type: "task.error",
					payload: { taskId, code, message },
				});
			}
		})();
	}, [token, taskId]);

	// 3. Auto-resize: report scrollHeight on every layout change.
	useEffect(() => {
		const report = () =>
			postEmbed(parentOriginRef.current, {
				type: "resize",
				payload: { height: document.documentElement.scrollHeight },
			});
		report();
		const ro = new ResizeObserver(report);
		ro.observe(document.documentElement);
		return () => ro.disconnect();
	}, [task, error]);

	const onSubmit = async () => {
		if (!token || !task) return;
		setSubmitting(true);
		setError(null);
		try {
			const body: CompleteTaskRequest = {
				response: value,
				completed_via_channel: "embed",
			};
			const result = await embedFetch<Task>(`/api/tasks/${taskId}/complete`, {
				token,
				method: "POST",
				body: JSON.stringify(body),
			});
			postEmbed(parentOriginRef.current, {
				type: "task.completed",
				payload: {
					taskId,
					response: result.response,
					completedAt: result.completed_at ?? new Date().toISOString(),
				},
			});
		} catch (e) {
			const code = e instanceof EmbedFetchError ? e.code : "internal";
			const message = e instanceof Error ? e.message : "Unknown error";
			setError(message);
			postEmbed(parentOriginRef.current, {
				type: "task.error",
				payload: { taskId, code, message },
			});
		} finally {
			setSubmitting(false);
		}
	};

	if (error) {
		return (
			<div className="p-6 font-mono text-sm text-fg-2">
				<p className="mb-2 text-red-400">Error</p>
				<p>{error}</p>
			</div>
		);
	}

	if (!task) {
		return (
			<div className="p-6 font-mono text-sm text-fg-2">Loading task...</div>
		);
	}

	return (
		<div className="mx-auto max-w-xl p-6">
			<h1 className="mb-4 font-mono text-lg font-medium">{task.task}</h1>
			{task.form_definition ? (
				<>
					<FormRenderer
						form={task.form_definition}
						value={value}
						onChange={setValue}
						disabled={submitting}
					/>
					<button
						type="button"
						onClick={() => void onSubmit()}
						disabled={submitting}
						className="mt-6 rounded-md bg-brand px-4 py-2 font-mono text-sm font-medium text-black disabled:opacity-50"
					>
						{submitting ? "Submitting..." : "Submit"}
					</button>
				</>
			) : (
				<p className="font-mono text-sm text-fg-2">No form defined for this task.</p>
			)}
		</div>
	);
}
