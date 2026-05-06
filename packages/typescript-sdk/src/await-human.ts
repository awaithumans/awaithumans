/**
 * awaitHuman — delegate a task to a human and await the result.
 *
 * Direct mode: creates a task on the server via POST /api/tasks, then
 * long-polls GET /api/tasks/{id}/poll until a terminal status or the
 * caller-side deadline expires. Reconnects each `POLL_INTERVAL_SECONDS`
 * to stay under gateway timeouts.
 *
 * For durable workflows, use the Temporal or LangGraph adapter — they
 * wrap this same primitive with engine-level persistence.
 *
 * Cross-runtime: only uses `fetch`, `AbortController`, `crypto.subtle`,
 * and `TextEncoder`. No node:* imports.
 */

import { zodToJsonSchema } from "zod-to-json-schema";

import {
	CREATE_TASK_TIMEOUT_MS,
	DEFAULT_SERVER_URL,
	MAX_TIMEOUT_MS,
	MIN_TIMEOUT_MS,
	POLL_FETCH_SLACK_SECONDS,
	POLL_INTERVAL_SECONDS,
} from "./internal/constants.js";
import { resolveDiscoveryConfig } from "./internal/discovery.js";
import { envVar } from "./internal/env.js";
import { fetchWithTimeout } from "./internal/fetch.js";
import { generateIdempotencyKey } from "./internal/idempotency.js";
import {
	type CreateTaskRequestWire,
	type CreateTaskResponseWire,
	type PollResponseWire,
	serializeAssignTo,
} from "./internal/wire.js";
import {
	MarketplaceNotAvailableError,
	PollError,
	SchemaValidationError,
	TaskCancelledError,
	TaskCreateError,
	TaskNotFoundError,
	TaskTimeoutError,
	TimeoutRangeError,
	VerificationExhaustedError,
} from "./errors.js";
import { extractForm } from "./forms/index.js";
import type { AwaitHumanOptions } from "./types/index.js";

export async function awaitHuman<TPayload, TResponse>(
	options: AwaitHumanOptions<TPayload, TResponse>,
): Promise<TResponse> {
	// ── Validate timeout range ──────────────────────────────────────────
	if (
		options.timeoutMs < MIN_TIMEOUT_MS ||
		options.timeoutMs > MAX_TIMEOUT_MS
	) {
		throw new TimeoutRangeError(options.timeoutMs);
	}

	// ── Validate payload against schema ─────────────────────────────────
	const payloadResult = options.payloadSchema.safeParse(options.payload);
	if (!payloadResult.success) {
		throw new SchemaValidationError("payload", payloadResult.error.message);
	}

	// ── Check for reserved marketplace assignTo ─────────────────────────
	if (
		options.assignTo &&
		typeof options.assignTo === "object" &&
		"marketplace" in options.assignTo
	) {
		throw new MarketplaceNotAvailableError();
	}

	// ── Resolve server URL + admin token ────────────────────────────────
	// Resolution priority (matches the Python SDK's `resolve_*` helpers):
	//   explicit option → env var → discovery file → default / undefined
	//
	// The discovery file lives at `~/.awaithumans-dev.json` and is
	// written by `awaithumans dev`. Reading it lets a developer run
	// `awaithumans dev` in one terminal and `npm start` in another
	// with zero env-var dance — same DX the Python SDK has.
	const discovery = await resolveDiscoveryConfig();
	const serverUrl = (
		options.serverUrl ??
		envVar("AWAITHUMANS_URL") ??
		discovery.url ??
		DEFAULT_SERVER_URL
	).replace(/\/$/, "");

	// `awaitHuman` is the agent path — task creation and polling are
	// admin-only on the server. The Temporal adapter already had this
	// pattern; direct mode missed it, so any admin-gated server
	// (including dev) 403'd unless callers hand-rolled a fetch wrapper.
	const apiKey =
		options.apiKey ??
		envVar("AWAITHUMANS_ADMIN_API_TOKEN") ??
		discovery.adminToken;

	// ── Generate idempotency key ────────────────────────────────────────
	const idempotencyKey =
		options.idempotencyKey ??
		(await generateIdempotencyKey(options.task, options.payload));

	// ── Build wire body ─────────────────────────────────────────────────
	const payloadJsonSchema = zodToJsonSchema(options.payloadSchema);
	const responseJsonSchema = zodToJsonSchema(options.responseSchema);
	const timeoutSeconds = Math.round(options.timeoutMs / 1000);

	// Synthesize a FormDefinition from the response schema where we can.
	// The server uses this to decide channel-specific rendering — most
	// notably whether the email channel emits Approve/Reject magic-link
	// buttons (single Switch primitive) or just a "Review in dashboard"
	// link-out (anything else). Returns null for shapes we can't yet
	// synthesize; the server falls back to JSON-schema rendering in
	// that case. See `forms/extract.ts` for coverage.
	const formDefinition = extractForm(options.responseSchema);

	const body: CreateTaskRequestWire = {
		task: options.task,
		payload: options.payload,
		payload_schema: payloadJsonSchema,
		response_schema: responseJsonSchema,
		form_definition: formDefinition,
		timeout_seconds: timeoutSeconds,
		idempotency_key: idempotencyKey,
		assign_to: serializeAssignTo(options.assignTo),
		notify: options.notify ?? null,
		verifier_config: options.verifier ?? null,
		redact_payload: options.redactPayload ?? false,
		callback_url: null,
	};

	// ── POST /api/tasks ─────────────────────────────────────────────────
	const task = await createTask(serverUrl, body, apiKey);

	// ── Long-poll until terminal ────────────────────────────────────────
	return pollUntilTerminal(
		serverUrl,
		task.id,
		options.task,
		timeoutSeconds,
		options.responseSchema,
		apiKey,
	);
}

// ─── Internals ──────────────────────────────────────────────────────────

function authHeaders(apiKey: string | undefined): Record<string, string> {
	return apiKey ? { Authorization: `Bearer ${apiKey}` } : {};
}

async function createTask(
	serverUrl: string,
	body: CreateTaskRequestWire,
	apiKey: string | undefined,
): Promise<CreateTaskResponseWire> {
	const resp = await fetchWithTimeout(
		`${serverUrl}/api/tasks`,
		{
			method: "POST",
			headers: {
				"Content-Type": "application/json",
				...authHeaders(apiKey),
			},
			body: JSON.stringify(body),
		},
		CREATE_TASK_TIMEOUT_MS,
		serverUrl,
	);

	if (resp.status !== 200 && resp.status !== 201) {
		throw new TaskCreateError(resp.status, await safeBodyText(resp));
	}

	return (await resp.json()) as CreateTaskResponseWire;
}

async function pollUntilTerminal<TResponse>(
	serverUrl: string,
	taskId: string,
	taskDescription: string,
	timeoutSeconds: number,
	// The response schema validates the server's returned response.
	// Typed as the user-supplied Zod schema to preserve inference.
	responseSchema: AwaitHumanOptions<unknown, TResponse>["responseSchema"],
	apiKey: string | undefined,
): Promise<TResponse> {
	const url = `${serverUrl}/api/tasks/${encodeURIComponent(
		taskId,
	)}/poll?timeout=${POLL_INTERVAL_SECONDS}`;
	const fetchTimeoutMs =
		(POLL_INTERVAL_SECONDS + POLL_FETCH_SLACK_SECONDS) * 1000;

	// Loop forever — the terminal-status branches below all either
	// return or throw. The server's poll endpoint holds each request
	// for ~POLL_INTERVAL_SECONDS and then returns the current status.
	// When the status is non-terminal we reconnect.
	while (true) {
		const resp = await fetchWithTimeout(
			url,
			{ headers: authHeaders(apiKey) },
			fetchTimeoutMs,
			serverUrl,
		);

		if (resp.status === 404) {
			throw new TaskNotFoundError(taskId);
		}
		if (resp.status !== 200) {
			throw new PollError(taskId, resp.status, await safeBodyText(resp));
		}

		const poll = (await resp.json()) as PollResponseWire;

		switch (poll.status) {
			case "completed": {
				const validated = responseSchema.safeParse(poll.response);
				if (!validated.success) {
					throw new SchemaValidationError(
						"response",
						validated.error.message,
					);
				}
				return validated.data;
			}
			case "timed_out":
				throw new TaskTimeoutError(taskDescription, timeoutSeconds * 1000);
			case "cancelled":
				throw new TaskCancelledError(taskDescription);
			case "verification_exhausted":
				throw new VerificationExhaustedError(
					taskDescription,
					poll.verification_attempt ?? 0,
				);
			// Everything else is non-terminal — keep polling.
			default:
				continue;
		}
	}
}

async function safeBodyText(resp: Response): Promise<string> {
	try {
		return await resp.text();
	} catch {
		return "";
	}
}
