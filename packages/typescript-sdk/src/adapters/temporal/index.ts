/**
 * Temporal adapter — signal-based durable HITL.
 *
 * Two halves, deployed in two different processes:
 *
 *   1. **Inside a Temporal workflow** — call `awaitHuman(...)` from
 *      this module. We register a signal handler scoped to the task's
 *      idempotency key, fire an activity that POSTs the task to the
 *      awaithumans server, then `workflow.condition()` blocks on
 *      either the signal arriving OR a workflow timer — both cost
 *      zero compute under Temporal's "park the workflow" model.
 *
 *   2. **Inside the user's web server** — `dispatchSignal(...)` is
 *      the framework-agnostic helper they wrap in a route. It
 *      verifies the HMAC, parses the body, and signals the workflow
 *      back to life.
 *
 * Mirrors `awaithumans.adapters.temporal` (Python). Wire format and
 * signal-name derivation are identical so a TypeScript workflow can
 * hand off a webhook to a Python receiver and vice versa.
 *
 * @example Workflow-side
 * ```ts
 * import { awaitHuman } from "awaithumans/temporal";
 * import { z } from "zod";
 *
 * export async function refundWorkflow(amount: number) {
 *   const decision = await awaitHuman({
 *     task: "Approve refund?",
 *     payloadSchema: z.object({ amount: z.number() }),
 *     payload: { amount },
 *     responseSchema: z.object({ approved: z.boolean() }),
 *     timeoutMs: 15 * 60 * 1000,
 *     callbackUrl: "https://my-app.com/awaithumans/cb?wf=" + workflowInfo().workflowId,
 *     serverUrl: "http://localhost:3001",
 *     apiKey: process.env.AWAITHUMANS_ADMIN_API_TOKEN,
 *   });
 *   return decision.approved;
 * }
 * ```
 *
 * @example Callback-side (in your web server, NOT the workflow)
 * ```ts
 * import { Connection, Client } from "@temporalio/client";
 * import { dispatchSignal } from "awaithumans/temporal";
 *
 * const client = new Client({ connection: await Connection.connect() });
 *
 * app.post("/awaithumans/cb", async (req, res) => {
 *   const wf = req.query.wf as string;
 *   try {
 *     await dispatchSignal({
 *       temporalClient: client,
 *       workflowId: wf,
 *       body: req.rawBody,  // raw bytes, not parsed
 *       signatureHeader: req.header("x-awaithumans-signature"),
 *     });
 *     res.sendStatus(200);
 *   } catch (e) {
 *     if (e instanceof Error && e.message.includes("signature")) res.sendStatus(401);
 *     else res.sendStatus(400);
 *   }
 * });
 * ```
 *
 * Requires:
 *   npm install @temporalio/workflow @temporalio/client
 *   (peer dependencies — declared as optional in this SDK so the
 *    base install doesn't pull in Temporal for users who don't need
 *    it.)
 */

import type { ZodType } from "zod";
import { zodToJsonSchema } from "zod-to-json-schema";

import {
	SchemaValidationError,
	TaskCancelledError,
	TaskTimeoutError,
	VerificationExhaustedError,
} from "../../errors.js";
import { generateIdempotencyKey } from "../../internal/idempotency.js";
import { serializeAssignTo } from "../../internal/wire.js";
import type { AssignTo, AwaitHumanOptions, VerifierConfig } from "../../types/index.js";

// Signal-name prefix — must match the Python adapter exactly.
// Cross-language receivers (Python web server signaling a TS
// workflow or vice versa) depend on this string being stable.
const SIGNAL_PREFIX = "awaithumans";

// Default timeout for the "create task" activity. Temporal retries
// activity failures automatically; this is just the per-attempt cap.
const DEFAULT_CREATE_ACTIVITY_TIMEOUT_MS = 30_000;

// ─── Workflow-side: awaitHuman ──────────────────────────────────────

export interface AwaitHumanTemporalOptions<TPayload, TResponse>
	extends AwaitHumanOptions<TPayload, TResponse> {
	/**
	 * URL where the awaithumans server should POST the completion
	 * webhook. The user's web server must host the callback receiver
	 * at this URL — see `dispatchSignal()` and the FastAPI/Express
	 * snippet in `examples/temporal/`.
	 */
	callbackUrl: string;

	/**
	 * Base URL of the awaithumans server (the human-facing one).
	 * In dev: `http://localhost:3001`. Required because workflows
	 * can't read environment variables directly — pass via input
	 * args or a config object.
	 */
	serverUrl: string;

	/** Bearer token for `serverUrl`. Same value the direct-mode SDK reads. */
	apiKey?: string;

	/** Per-attempt timeout for the create-task activity. Default: 30s. */
	createActivityTimeoutMs?: number;
}

interface CreateTaskActivityInput {
	serverUrl: string;
	apiKey: string | undefined;
	body: Record<string, unknown>;
}

interface CreateTaskActivityResult {
	id: string;
	idempotencyKey: string;
}

// The signal payload the user's web server delivers — mirrors the
// awaithumans webhook body exactly.
interface CompletionSignal {
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

function signalName(idempotencyKey: string): string {
	return `${SIGNAL_PREFIX}:${idempotencyKey}`;
}

/**
 * Awaitable: suspend the running Temporal workflow until a human
 * completes the task. See module docstring for the architecture.
 *
 * @throws TaskTimeoutError if `timeoutMs` elapses with no completion.
 * @throws TaskCancelledError if the task was cancelled (server side).
 * @throws VerificationExhaustedError if the verifier rejected every attempt.
 * @throws SchemaValidationError if the human's response doesn't match `responseSchema`.
 */
export async function awaitHuman<TPayload, TResponse>(
	options: AwaitHumanTemporalOptions<TPayload, TResponse>,
): Promise<TResponse> {
	// Lazy require: peer dep, optional. Importing temporalio at the
	// top of this module would force every TS SDK user to install it.
	const wf = await loadWorkflowApi();

	const idempotencyKey =
		options.idempotencyKey ??
		`temporal:${(await generateIdempotencyKey(options.task, options.payload)).slice(0, 32)}`;
	const signal = signalName(idempotencyKey);

	// Captured by the closure below. We use a 1-element wrapper
	// because TypeScript doesn't let inner functions rebind outer
	// scalars without a class.
	const received: { value: CompletionSignal | null } = { value: null };

	wf.setHandler<[CompletionSignal]>(
		wf.defineSignal<[CompletionSignal]>(signal),
		(payload) => {
			received.value = payload;
		},
	);

	const payloadJsonSchema = zodToJsonSchema(options.payloadSchema);
	const responseJsonSchema = zodToJsonSchema(options.responseSchema);
	const timeoutSeconds = Math.round(options.timeoutMs / 1000);

	// Serialize the create-task wire body in the workflow (deterministic),
	// then ship it through an activity (where HTTP is allowed).
	const body = {
		task: options.task,
		payload: options.payload,
		payload_schema: payloadJsonSchema,
		response_schema: responseJsonSchema,
		form_definition: null,
		timeout_seconds: timeoutSeconds,
		idempotency_key: idempotencyKey,
		assign_to: serializeAssignTo(options.assignTo as AssignTo | undefined),
		notify: options.notify ?? null,
		verifier_config:
			(options.verifier as VerifierConfig | undefined) ?? null,
		redact_payload: options.redactPayload ?? false,
		callback_url: options.callbackUrl,
	};

	await wf.executeActivity<CreateTaskActivityInput, CreateTaskActivityResult>(
		"awaithumansCreateTask",
		{
			args: [
				{
					serverUrl: options.serverUrl,
					apiKey: options.apiKey,
					body,
				},
			],
			startToCloseTimeout:
				options.createActivityTimeoutMs ?? DEFAULT_CREATE_ACTIVITY_TIMEOUT_MS,
		},
	);

	// Race: signal received OR timeout. `wf.condition` returns true
	// when the predicate fires, false when it timed out.
	const completed = await wf.condition(
		() => received.value !== null,
		options.timeoutMs,
	);
	if (!completed || received.value === null) {
		throw new TaskTimeoutError(options.task, options.timeoutMs);
	}

	const status = received.value.status;
	if (status === "completed") {
		const validated = options.responseSchema.safeParse(received.value.response);
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
			received.value.verification_attempt ?? 0,
		);
	}
	throw new Error(
		`Temporal adapter saw unknown terminal status '${status}' for task '${options.task}'`,
	);
}

/**
 * The activity that POSTs the task to the awaithumans server.
 *
 * Register this on your Temporal worker alongside any of your own
 * activities:
 *
 * ```ts
 * import { Worker } from "@temporalio/worker";
 * import { awaithumansCreateTask } from "awaithumans/temporal";
 *
 * const worker = await Worker.create({
 *   workflowsPath: require.resolve("./workflows"),
 *   activities: { ...myActivities, awaithumansCreateTask },
 *   taskQueue: "my-q",
 * });
 * ```
 *
 * Activities run OUTSIDE the workflow sandbox — `fetch` and the
 * Node stdlib are available here. Temporal's automatic retries
 * cover transient server failures.
 */
export async function awaithumansCreateTask(
	input: CreateTaskActivityInput,
): Promise<CreateTaskActivityResult> {
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
		throw new Error(
			`awaithumans server rejected task creation (HTTP ${resp.status}): ${text.slice(
				0,
				500,
			)}`,
		);
	}

	const data = (await resp.json()) as { id: string; idempotency_key: string };
	return { id: data.id, idempotencyKey: data.idempotency_key };
}

// ─── User-web-server-side: dispatchSignal ───────────────────────────

/**
 * Minimal interface satisfied by `Client` from `@temporalio/client`.
 * Typed as a structural interface so this module doesn't need to
 * import the heavy class — keeps `dispatchSignal` testable with a
 * fake.
 */
export interface TemporalClientLike {
	getHandle(workflowId: string): {
		signal(name: string, arg: unknown): Promise<void>;
	};
}

export interface DispatchSignalOptions {
	/** Connected `@temporalio/client` Client. */
	temporalClient: TemporalClientLike;

	/**
	 * The workflow ID to signal. Read from the request URL — typically
	 * a query param (`?wf=...`) the workflow encoded into
	 * `callbackUrl` when it called `awaitHuman`.
	 */
	workflowId: string;

	/** The raw request body bytes — needed for HMAC verification. */
	body: ArrayBuffer | Uint8Array | string;

	/** The `X-Awaithumans-Signature` header value (or null/undefined). */
	signatureHeader: string | null | undefined;

	/**
	 * The HMAC key used to verify the signature. Must match
	 * AWAITHUMANS_PAYLOAD_KEY on the awaithumans server (which
	 * derives the webhook key from it via HKDF). Most users read
	 * this from `process.env.AWAITHUMANS_PAYLOAD_KEY`.
	 *
	 * Cross-language note: the Python server uses HKDF with salt
	 * `b"awaithumans-webhook-v1"` and info `b"v1"` over PAYLOAD_KEY
	 * to derive the actual signing key. To verify here, do the same
	 * HKDF-SHA256 on the Node side; helpers below.
	 */
	payloadKey: string;
}

/**
 * Verify a webhook signature and signal the matching workflow.
 *
 * Wraps a few lines of route boilerplate so the user's web server
 * stays small. See module docstring for the Express snippet. Throws:
 *
 *   - `Error("Invalid awaithumans webhook signature.")` — wrap to 401
 *   - `Error("Webhook body is not JSON: ...")` — wrap to 400
 *   - `Error("Webhook missing idempotency_key: ...")` — wrap to 400
 */
export async function dispatchSignal(
	options: DispatchSignalOptions,
): Promise<void> {
	const bodyBytes = toUint8Array(options.body);
	const ok = await verifySignature({
		body: bodyBytes,
		signatureHeader: options.signatureHeader,
		payloadKey: options.payloadKey,
	});
	if (!ok) {
		throw new Error("Invalid awaithumans webhook signature.");
	}

	let payload: { idempotency_key?: string };
	try {
		payload = JSON.parse(new TextDecoder().decode(bodyBytes));
	} catch (cause) {
		throw new Error(`Webhook body is not JSON: ${(cause as Error).message}`);
	}
	const idem = payload.idempotency_key;
	if (typeof idem !== "string" || !idem) {
		throw new Error(
			`Webhook missing idempotency_key: ${JSON.stringify(payload)}`,
		);
	}

	const handle = options.temporalClient.getHandle(options.workflowId);
	await handle.signal(signalName(idem), payload);
}

// ─── HMAC verification (matches the Python server's HKDF derivation) ─

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
 * who want to drive the dispatch loop themselves can verify the
 * same way the SDK helper does.
 */
export async function signBody(
	body: Uint8Array,
	payloadKey: string,
): Promise<string> {
	const hkdfKey = await deriveHmacKey(payloadKey);
	// Web Crypto's BufferSource type narrowed in recent TS releases —
	// Uint8Array<ArrayBufferLike> isn't directly assignable. The cast
	// below is safe (it's the right runtime shape) and matches what
	// the runtime accepts.
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
	// Mirror the Python server's HKDF parameters exactly. Salt and
	// info bytes are the source of truth for cross-language compat.
	//
	// PAYLOAD_KEY on the Python side is decoded from urlsafe-b64 to
	// 32 raw bytes BEFORE HKDF (see server/core/encryption.py:get_key).
	// We do the same here so a workflow signed in TS verifies on a
	// Python receiver and vice versa.
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

/**
 * URL-safe base64 decode that tolerates missing padding — matches
 * Python's `base64.urlsafe_b64decode(padded)` semantics. The
 * awaithumans server's PAYLOAD_KEY is typically generated via
 * `secrets.token_urlsafe(32)` which produces unpadded output.
 */
function base64UrlDecode(s: string): Uint8Array {
	// Restore padding to a multiple of 4.
	const padded = s + "=".repeat((4 - (s.length % 4)) % 4);
	// Convert URL-safe alphabet (`-_`) to standard (`+/`) before atob.
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

// ─── Lazy peer-dep loader ───────────────────────────────────────────

interface WorkflowApi {
	defineSignal<TArgs extends unknown[]>(
		name: string,
	): { name: string };
	setHandler<TArgs extends unknown[]>(
		def: { name: string },
		handler: (...args: TArgs) => void,
	): void;
	executeActivity<TInput, TOut>(
		name: string,
		opts: { args: [TInput]; startToCloseTimeout: number },
	): Promise<TOut>;
	condition(
		predicate: () => boolean,
		timeoutMs?: number,
	): Promise<boolean>;
}

let cachedWorkflowApi: WorkflowApi | null = null;

async function loadWorkflowApi(): Promise<WorkflowApi> {
	if (cachedWorkflowApi !== null) return cachedWorkflowApi;
	try {
		// Dynamic import so the base SDK doesn't pull Temporal in at
		// load time. The peer dep is declared optional in
		// package.json; users who never call awaitHuman from a workflow
		// don't need to install it. Module specifier is constructed at
		// runtime so `tsc` in a base install (no @temporalio installed)
		// doesn't complain about a missing module.
		const moduleName = "@temporalio/workflow";
		const mod = (await import(/* @vite-ignore */ moduleName)) as unknown as WorkflowApi;
		cachedWorkflowApi = mod;
		return mod;
	} catch (cause) {
		throw new Error(
			"The Temporal adapter requires `@temporalio/workflow`.\n" +
				"Install with: npm install @temporalio/workflow @temporalio/client\n" +
				`Underlying error: ${(cause as Error).message}`,
		);
	}
}
