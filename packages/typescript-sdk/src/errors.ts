import { DOCS_ROADMAP_URL, DOCS_TROUBLESHOOTING_URL } from "./internal/constants";

export interface AwaitHumansErrorOptions {
	code: string;
	message: string;
	hint: string;
	docsUrl: string;
}

export class AwaitHumansError extends Error {
	readonly code: string;
	readonly hint: string;
	readonly docsUrl: string;

	constructor(options: AwaitHumansErrorOptions) {
		const fullMessage = [
			options.message,
			"",
			options.hint,
			"",
			`Docs: ${options.docsUrl}`,
		].join("\n");

		super(fullMessage);
		this.name = "AwaitHumansError";
		this.code = options.code;
		this.hint = options.hint;
		this.docsUrl = options.docsUrl;
	}
}

export class TaskTimeoutError extends AwaitHumansError {
	constructor(task: string, timeoutMs: number) {
		super({
			code: "TIMEOUT_EXCEEDED",
			message: `Task "${task}" timed out after ${Math.round(timeoutMs / 1000)} seconds.`,
			hint: [
				"No human completed the task. Check:",
				"  1. Is your notification channel configured? (AWAITHUMANS_SLACK_WEBHOOK)",
				"  2. Did the assigned human receive the notification?",
				"  3. Consider increasing timeoutMs if humans need more time.",
			].join("\n"),
			docsUrl: `${DOCS_TROUBLESHOOTING_URL}#timeout`,
		});
	}
}

export class SchemaValidationError extends AwaitHumansError {
	constructor(field: "payload" | "response", details: string) {
		super({
			code: "SCHEMA_VALIDATION_FAILED",
			message: `The ${field} does not match the provided schema.`,
			hint: [
				`Validation error: ${details}`,
				"",
				`Check that your ${field} conforms to the ${field}Schema you provided.`,
				"All payloads and responses must be JSON-serializable.",
			].join("\n"),
			docsUrl: `${DOCS_TROUBLESHOOTING_URL}#schema-validation`,
		});
	}
}

export class TimeoutRangeError extends AwaitHumansError {
	constructor(timeoutMs: number) {
		super({
			code: "TIMEOUT_OUT_OF_RANGE",
			message: `timeoutMs must be between 60,000 (1 minute) and 2,592,000,000 (30 days). Got: ${timeoutMs}.`,
			hint: [
				"awaitHuman is designed for human response times.",
				"  Minimum: 60,000 ms (1 minute)",
				"  Maximum: 2,592,000,000 ms (30 days)",
				"For sub-minute timeouts, use a promise or a queue, not HITL.",
			].join("\n"),
			docsUrl: `${DOCS_TROUBLESHOOTING_URL}#timeout-range`,
		});
	}
}

export class TaskAlreadyTerminalError extends AwaitHumansError {
	constructor(taskId: string, status: string) {
		super({
			code: "TASK_ALREADY_TERMINAL",
			message: `Task "${taskId}" is already in terminal status "${status}".`,
			hint: "The task was completed, timed out, or cancelled before this action could be processed. This can happen in race conditions between the timeout and a human submission.",
			docsUrl: `${DOCS_TROUBLESHOOTING_URL}#task-already-terminal`,
		});
	}
}

export class VerificationExhaustedError extends AwaitHumansError {
	constructor(task: string, maxAttempts: number) {
		super({
			code: "VERIFICATION_EXHAUSTED",
			message: `Task "${task}" failed verification ${maxAttempts} times.`,
			hint: [
				"The human's response was rejected by the verifier on every attempt.",
				"Check your verifier instructions — they may be too strict.",
				"Consider increasing maxAttempts or adjusting the verification criteria.",
			].join("\n"),
			docsUrl: `${DOCS_TROUBLESHOOTING_URL}#verification-exhausted`,
		});
	}
}

/** @reserved Phase 4 */
export class MarketplaceNotAvailableError extends AwaitHumansError {
	constructor() {
		super({
			code: "MARKETPLACE_NOT_AVAILABLE",
			message: 'The workforce marketplace (assignTo: { marketplace: true }) is not yet available.',
			hint: "The marketplace is coming in a future release. For now, assign tasks to specific humans, pools, or roles.",
			docsUrl: `${DOCS_ROADMAP_URL}#marketplace`,
		});
	}
}

// ─── Runtime errors returned by the server ───────────────────────────

export class TaskNotFoundError extends AwaitHumansError {
	constructor(taskId: string) {
		super({
			code: "TASK_NOT_FOUND",
			message: `Task "${taskId}" not found on the server.`,
			hint:
				"The task may have been deleted or the server was restarted with a fresh database.",
			docsUrl: `${DOCS_TROUBLESHOOTING_URL}#task-not-found`,
		});
	}
}

export class TaskCancelledError extends AwaitHumansError {
	constructor(task: string) {
		super({
			code: "TASK_CANCELLED",
			message: `Task "${task}" was cancelled.`,
			hint: "The task was cancelled by an admin or another agent before a human completed it.",
			docsUrl: `${DOCS_TROUBLESHOOTING_URL}#task-cancelled`,
		});
	}
}

export class TaskCreateError extends AwaitHumansError {
	constructor(status: number, serverBody: string) {
		super({
			code: "TASK_CREATE_FAILED",
			message: `Failed to create task on the server (HTTP ${status}).`,
			hint: `Server response: ${serverBody.slice(0, 500)}`,
			docsUrl: `${DOCS_TROUBLESHOOTING_URL}#task-create-failed`,
		});
	}
}

export class PollError extends AwaitHumansError {
	constructor(taskId: string, status: number, serverBody: string) {
		super({
			code: "POLL_FAILED",
			message: `Failed to poll task "${taskId}" (HTTP ${status}).`,
			hint: `Server response: ${serverBody.slice(0, 500)}`,
			docsUrl: `${DOCS_TROUBLESHOOTING_URL}#poll-failed`,
		});
	}
}

export class ServerUnreachableError extends AwaitHumansError {
	constructor(serverUrl: string, cause: unknown) {
		super({
			code: "SERVER_UNREACHABLE",
			message: `Could not reach the awaithumans server at ${serverUrl}.`,
			hint: [
				"Check:",
				"  1. Is the server running? (awaithumans dev)",
				"  2. Is the URL correct? Override with `serverUrl` or AWAITHUMANS_URL.",
				`  3. Underlying error: ${String(cause)}`,
			].join("\n"),
			docsUrl: `${DOCS_TROUBLESHOOTING_URL}#server-unreachable`,
		});
	}
}
