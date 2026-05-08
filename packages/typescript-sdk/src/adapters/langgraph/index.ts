/**
 * LangGraph adapter — interrupt/resume durable HITL.
 *
 * Two halves, deployed in two different processes (or two paths inside
 * one process):
 *
 *   1. **Inside a graph node** — call `awaitHuman(...)` from this
 *      module. We POST the task to the awaithumans server, then call
 *      `interrupt(...)` from `@langchain/langgraph`. The graph throws
 *      a `GraphInterrupt`; the caller (your application) catches that
 *      at the `graph.invoke()` boundary, persists nothing of its own
 *      (LangGraph's checkpointer already saved state), and returns to
 *      its event loop. The process can crash and the state survives.
 *
 *   2. **Inside the user's web server** — `createLangGraphCallbackHandler`
 *      returns a framework-agnostic handler. It verifies the HMAC,
 *      extracts the thread id from the request URL (which the
 *      workflow encoded into `callbackUrl` when it called awaitHuman),
 *      and re-invokes the graph with `new Command({resume})`. The
 *      replayed `interrupt(...)` returns the response and the node
 *      continues like nothing happened.
 *
 * Mirrors `awaithumans.adapters.langgraph` (Python). Wire format
 * matches the Temporal adapter so a single awaithumans server can
 * back any mix of frameworks.
 *
 * @example Graph-side
 * ```ts
 * import { awaitHuman } from "awaithumans/langgraph";
 * import { z } from "zod";
 *
 * async function approveNode(state: RefundState, config: RunnableConfig) {
 *   const decision = await awaitHuman({
 *     task: "Approve refund?",
 *     payloadSchema: z.object({ amount: z.number() }),
 *     payload: { amount: state.amount },
 *     responseSchema: z.object({ approved: z.boolean() }),
 *     timeoutMs: 15 * 60 * 1000,
 *     callbackUrl:
 *       "https://my-app.com/awaithumans/cb?thread=" +
 *       config.configurable!.thread_id,
 *     serverUrl: "http://localhost:3001",
 *     apiKey: process.env.AWAITHUMANS_ADMIN_API_TOKEN,
 *   });
 *   return { decision: decision.approved };
 * }
 * ```
 *
 * @example Callback-side (in your web server)
 * ```ts
 * import { Hono } from "hono";
 * import { createLangGraphCallbackHandler } from "awaithumans/langgraph";
 *
 * const app = new Hono();
 * const handle = createLangGraphCallbackHandler({
 *   graph,
 *   payloadKey: process.env.AWAITHUMANS_PAYLOAD_KEY!,
 * });
 *
 * app.post("/awaithumans/cb", async (c) => {
 *   const thread = c.req.query("thread");
 *   if (!thread) return c.text("missing thread", 400);
 *   const body = await c.req.arrayBuffer();
 *   const sig = c.req.header("x-awaithumans-signature");
 *   const status = await handle({ threadId: thread, body, signatureHeader: sig });
 *   return c.text(status === 200 ? "ok" : "bad", status);
 * });
 * ```
 *
 * Requires:
 *   npm install @langchain/langgraph
 *   (peer dependency — declared as optional in this SDK so the base
 *    install doesn't pull LangGraph in for users who don't need it.)
 */

import { zodToJsonSchema } from "zod-to-json-schema";

import {
	SchemaValidationError,
	TaskCancelledError,
	TaskCreateError,
	TaskTimeoutError,
	VerificationExhaustedError,
} from "../../errors.js";
import { extractForm } from "../../forms/index.js";
import { generateIdempotencyKey } from "../../internal/idempotency.js";
import {
	serializeAssignTo,
	serializeVerifierConfig,
} from "../../internal/wire.js";
import type { AssignTo, AwaitHumanOptions, VerifierConfig } from "../../types/index.js";

// Idempotency-key prefix — namespace so a content-hash collision
// across adapters can't accidentally land on the same task. Mirrors
// `temporal:` in the Temporal adapter.
const IDEMPOTENCY_PREFIX = "langgraph";

// ─── Graph-side: awaitHuman ─────────────────────────────────────────

export interface AwaitHumanLangGraphOptions<TPayload, TResponse>
	extends AwaitHumanOptions<TPayload, TResponse> {
	/**
	 * Where the awaithumans server should POST the completion webhook.
	 * Encode the LangGraph thread id in this URL so the callback
	 * handler can resume the right graph instance:
	 *   `https://my-app.com/awaithumans/cb?thread=${threadId}`
	 */
	callbackUrl: string;

	/**
	 * Base URL of the awaithumans server. In dev: `http://localhost:3001`.
	 * Required because nodes can't reach for env vars in a sandboxed
	 * runtime — pass via your graph state, your runnable config, or
	 * read once at module load.
	 */
	serverUrl: string;

	/** Bearer token for `serverUrl`. Same value the direct-mode SDK reads. */
	apiKey?: string;
}

// The interrupt payload shape — what comes out of `interrupt()` when
// the graph is paused, before resume. The user's web UI / dashboard
// can read this to render "task X is pending review".
export interface AwaitHumanInterrupt {
	taskId: string;
	idempotencyKey: string;
	task: string;
	payload: unknown;
	callbackUrl: string;
}

// What the resume value is expected to look like — exactly the shape
// the awaithumans webhook body has, which is what `dispatchResume`
// passes through to `Command({resume: ...})` below. Receiving the
// full payload (not just the response) means the node can disambiguate
// `completed` vs `timed_out` vs `cancelled` and surface the right
// typed error.
export interface CompletionResume {
	task_id?: string;
	idempotency_key?: string;
	status?: string;
	response?: unknown;
	completed_at?: string | null;
	timed_out_at?: string | null;
	completed_by_email?: string | null;
	completed_via_channel?: string | null;
	verification_attempt?: number;
}

// Static import: the interrupt symbol IS LangGraph's resume protocol.
// We can't dynamic-import inside a node call (interrupt has to be the
// EXACT module instance the host runtime uses, like CancellationScope
// in Temporal — see PR #60 for the analogous lesson there).
import { interrupt } from "@langchain/langgraph";

/**
 * Awaitable: pause the running graph until a human completes the task.
 * See module docstring for the architecture.
 *
 * @throws TaskCreateError if the awaithumans server rejects the create call.
 * @throws TaskTimeoutError if the server reports `timed_out` on resume.
 * @throws TaskCancelledError if the server reports `cancelled` on resume.
 * @throws VerificationExhaustedError if the verifier rejected every attempt.
 * @throws SchemaValidationError if the human's response doesn't match `responseSchema`.
 */
export async function awaitHuman<TPayload, TResponse>(
	options: AwaitHumanLangGraphOptions<TPayload, TResponse>,
): Promise<TResponse> {
	const idempotencyKey =
		options.idempotencyKey ??
		`${IDEMPOTENCY_PREFIX}:${(
			await generateIdempotencyKey(options.task, options.payload)
		).slice(0, 32)}`;

	// Create the task on the server FIRST. It's idempotent on the
	// `idempotency_key` so if this node replays after a checkpoint
	// restore, the second create returns the same task without
	// duplicating notifications.
	//
	// We do this BEFORE interrupt() so the task is visible to the
	// human (Slack ping, dashboard, email) immediately. If we put
	// interrupt() first, the graph would pause before the task even
	// existed — a tree-falls-in-the-forest race.
	const payloadJsonSchema = zodToJsonSchema(options.payloadSchema);
	const responseJsonSchema = zodToJsonSchema(options.responseSchema);
	const timeoutSeconds = Math.round(options.timeoutMs / 1000);
	// Derive form_definition from responseSchema so the dashboard can
	// render the Approve / Reject form when an operator opens or
	// claims the task. Direct-mode SDK does the same in
	// `await-human.ts`. Without this, dashboard-driven approval has
	// nothing to render.
	const formDefinition = extractForm(options.responseSchema);

	const body = {
		task: options.task,
		payload: options.payload,
		payload_schema: payloadJsonSchema,
		response_schema: responseJsonSchema,
		form_definition: formDefinition,
		timeout_seconds: timeoutSeconds,
		idempotency_key: idempotencyKey,
		assign_to: serializeAssignTo(options.assignTo as AssignTo | undefined),
		notify: options.notify ?? null,
		verifier_config: serializeVerifierConfig(
			options.verifier as VerifierConfig | undefined,
		),
		redact_payload: options.redactPayload ?? false,
		callback_url: options.callbackUrl,
	};

	const task = await createTaskOnServer({
		serverUrl: options.serverUrl,
		apiKey: options.apiKey,
		body,
	});

	// `interrupt()` does double duty: on first run it throws a
	// GraphInterrupt (caller catches at the .invoke boundary, graph
	// pauses, checkpointer persists state); on resume the same line
	// returns the value passed via `Command({resume: …})`. So this
	// "await" actually resolves on the SECOND graph invocation, not
	// the first.
	const resumeValue = interrupt<AwaitHumanInterrupt, CompletionResume>({
		taskId: task.id,
		idempotencyKey,
		task: options.task,
		payload: options.payload,
		callbackUrl: options.callbackUrl,
	});

	const status = resumeValue.status;
	if (status === "completed") {
		const validated = options.responseSchema.safeParse(resumeValue.response);
		if (!validated.success) {
			throw new SchemaValidationError("response", validated.error.message);
		}
		return validated.data;
	}
	if (status === "timed_out") {
		throw new TaskTimeoutError(options.task, options.timeoutMs);
	}
	if (status === "cancelled") {
		throw new TaskCancelledError(options.task);
	}
	if (status === "verification_exhausted") {
		throw new VerificationExhaustedError(
			options.task,
			resumeValue.verification_attempt ?? 0,
		);
	}
	throw new Error(
		`LangGraph adapter saw unknown terminal status '${status ?? "<missing>"}' for task '${options.task}'`,
	);
}

interface CreateTaskInput {
	serverUrl: string;
	apiKey: string | undefined;
	body: Record<string, unknown>;
}

interface CreateTaskResult {
	id: string;
	idempotencyKey: string;
}

async function createTaskOnServer(input: CreateTaskInput): Promise<CreateTaskResult> {
	const headers: Record<string, string> = {
		"Content-Type": "application/json",
	};
	if (input.apiKey) {
		headers["Authorization"] = `Bearer ${input.apiKey}`;
	}

	const url = `${input.serverUrl.replace(/\/$/, "")}/api/tasks`;
	const resp = await fetch(url, {
		method: "POST",
		headers,
		body: JSON.stringify(input.body),
	});

	if (resp.status !== 200 && resp.status !== 201) {
		const text = await resp.text();
		throw new TaskCreateError(resp.status, text);
	}
	const data = (await resp.json()) as { id: string; idempotency_key: string };
	return { id: data.id, idempotencyKey: data.idempotency_key };
}

// ─── User-web-server-side: createLangGraphCallbackHandler ────────────

/**
 * Minimal interface satisfied by `CompiledStateGraph` from
 * `@langchain/langgraph`. Typed structurally so the SDK doesn't pull
 * the heavy class for users who only call awaitHuman from a node and
 * never wire up the callback handler — and so tests can pass a fake.
 */
export interface LangGraphInvokable {
	invoke(
		input: unknown,
		config?: { configurable?: Record<string, unknown> } & Record<
			string,
			unknown
		>,
	): Promise<unknown>;
}

/**
 * Minimal interface for the `Command` constructor we accept. Same
 * reason as above — structural so callers can pass either the real
 * `Command` from `@langchain/langgraph` or a wrapper.
 */
export interface CommandConstructorLike {
	new (params: { resume: unknown }): unknown;
}

export interface CallbackHandlerOptions {
	/**
	 * The compiled graph that runs your application. The handler
	 * `invoke`s it once per webhook to resume the paused thread.
	 */
	graph: LangGraphInvokable;

	/**
	 * The `Command` class from `@langchain/langgraph`. Pass it in
	 * directly (`Command`) — we accept it as a parameter so the SDK
	 * itself doesn't need to import the runtime symbol; that import
	 * happens inside YOUR app, in YOUR module-resolution tree, which
	 * sidesteps the dual-package hazard the Temporal adapter ran into.
	 */
	command: CommandConstructorLike;

	/**
	 * The HMAC key the awaithumans server signs webhooks with. Read
	 * from `AWAITHUMANS_PAYLOAD_KEY` on the server side; receivers
	 * MUST have the same value. The server uses HKDF-SHA256 with
	 * salt `b"awaithumans-webhook-v1"` and info `b"v1"` over this
	 * key to derive the actual signing key — we mirror that derivation
	 * below.
	 */
	payloadKey: string;
}

export interface HandleCallbackInput {
	/** The LangGraph thread id to resume. Read from a query param. */
	threadId: string;

	/** Raw request body bytes — needed for HMAC verification. */
	body: ArrayBuffer | Uint8Array | string;

	/** The `X-Awaithumans-Signature` header value (or null/undefined). */
	signatureHeader: string | null | undefined;
}

export interface HandleCallbackResult {
	/** HTTP-status-shaped outcome — let the caller wire it to their framework. */
	status: number;
	error?: string;
}

/**
 * Build a framework-agnostic webhook handler closed over your graph.
 * Wrap the returned function in a Hono / Express / Fastify route.
 *
 * The handler:
 *   1. Verifies the HMAC signature against `payloadKey`. Bad sig → 401.
 *   2. Parses the body. Bad JSON → 400.
 *   3. Calls `graph.invoke(new Command({resume: <body>}), {configurable:{thread_id}})`.
 *   4. Returns 200 on success. Any thrown error → 500.
 *
 * We pass the FULL webhook body as the resume value (not just
 * `response`) so the node can branch on `status` and surface the
 * right typed error for timed-out / cancelled / verification-exhausted.
 */
export function createLangGraphCallbackHandler(
	options: CallbackHandlerOptions,
): (input: HandleCallbackInput) => Promise<HandleCallbackResult> {
	return async function handleCallback(
		input: HandleCallbackInput,
	): Promise<HandleCallbackResult> {
		const bodyBytes = toUint8Array(input.body);
		const ok = await verifySignature({
			body: bodyBytes,
			signatureHeader: input.signatureHeader,
			payloadKey: options.payloadKey,
		});
		if (!ok) {
			return { status: 401, error: "Invalid awaithumans webhook signature." };
		}

		let payload: CompletionResume;
		try {
			payload = JSON.parse(new TextDecoder().decode(bodyBytes));
		} catch (cause) {
			return {
				status: 400,
				error: `Webhook body is not JSON: ${(cause as Error).message}`,
			};
		}

		try {
			const command = new options.command({ resume: payload });
			await options.graph.invoke(command, {
				configurable: { thread_id: input.threadId },
			});
		} catch (cause) {
			return {
				status: 500,
				error: `Graph resume failed: ${(cause as Error).message}`,
			};
		}

		return { status: 200 };
	};
}

// ─── HMAC verification (matches the Python server's HKDF derivation) ─
//
// Identical to the Temporal adapter's verify path — kept inline rather
// than imported so the langgraph subpath stays a self-contained leaf.
// If we grow a third adapter, this should move to `internal/webhook.ts`.

interface VerifySignatureInput {
	body: Uint8Array;
	signatureHeader: string | null | undefined;
	payloadKey: string;
}

async function verifySignature(input: VerifySignatureInput): Promise<boolean> {
	if (!input.signatureHeader) return false;
	const expected = await signBody(input.body, input.payloadKey);
	const supplied = input.signatureHeader.startsWith("sha256=")
		? input.signatureHeader
		: `sha256=${input.signatureHeader}`;
	return constantTimeEqual(expected, supplied);
}

/**
 * Compute the `sha256=<hex>` signature over `body`. Public so users
 * who want to drive the dispatch loop themselves can verify the same
 * way the SDK helper does.
 */
export async function signBody(
	body: Uint8Array,
	payloadKey: string,
): Promise<string> {
	const hkdfKey = await deriveHmacKey(payloadKey);
	const cryptoKey = await crypto.subtle.importKey(
		"raw",
		hkdfKey as unknown as BufferSource,
		{ name: "HMAC", hash: "SHA-256" },
		false,
		["sign"],
	);
	const sig = await crypto.subtle.sign(
		"HMAC",
		cryptoKey,
		body as unknown as BufferSource,
	);
	return `sha256=${bytesToHex(new Uint8Array(sig))}`;
}

async function deriveHmacKey(payloadKey: string): Promise<Uint8Array> {
	const enc = new TextEncoder();
	const rawIkm = base64UrlDecode(payloadKey);
	const ikmRaw = await crypto.subtle.importKey(
		"raw",
		rawIkm as unknown as BufferSource,
		{ name: "HKDF" },
		false,
		["deriveBits"],
	);
	const derived = await crypto.subtle.deriveBits(
		{
			name: "HKDF",
			hash: "SHA-256",
			salt: enc.encode("awaithumans-webhook-v1") as unknown as BufferSource,
			info: enc.encode("v1") as unknown as BufferSource,
		},
		ikmRaw,
		32 * 8, // 32 bytes
	);
	return new Uint8Array(derived);
}

function constantTimeEqual(a: string, b: string): boolean {
	if (a.length !== b.length) return false;
	let result = 0;
	for (let i = 0; i < a.length; i++) {
		result |= a.charCodeAt(i) ^ b.charCodeAt(i);
	}
	return result === 0;
}

function bytesToHex(bytes: Uint8Array): string {
	return Array.from(bytes, (b) => b.toString(16).padStart(2, "0")).join("");
}

function base64UrlDecode(s: string): Uint8Array {
	const padded = s + "=".repeat((4 - (s.length % 4)) % 4);
	const normalized = padded.replace(/-/g, "+").replace(/_/g, "/");
	const binary = atob(normalized);
	const bytes = new Uint8Array(binary.length);
	for (let i = 0; i < binary.length; i++) bytes[i] = binary.charCodeAt(i);
	return bytes;
}

function toUint8Array(body: ArrayBuffer | Uint8Array | string): Uint8Array {
	if (body instanceof Uint8Array) return body;
	if (body instanceof ArrayBuffer) return new Uint8Array(body);
	return new TextEncoder().encode(body);
}
