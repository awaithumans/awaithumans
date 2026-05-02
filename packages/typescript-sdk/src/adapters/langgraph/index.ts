/**
 * LangGraph adapter — interrupt/resume durable HITL.
 *
 * Mirrors `awaithumans.adapters.langgraph` (Python). The descriptor
 * shape, idempotency-key prefix, and wire-level API contract are
 * identical so a TypeScript driver can resume a graph that was
 * paused under Python (and vice versa).
 *
 * Two halves, both in the SAME process — LangGraph is library-
 * style, not a separate worker:
 *
 *   1. **Inside a graph node** — call `awaitHuman(...)`. We package
 *      the task descriptor and call LangGraph's `interrupt(...)`,
 *      which raises `GraphInterrupt` and parks the node.
 *
 *   2. **In the driver loop** — call `driveHumanLoop(graph, input,
 *      config, ...)`. The driver streams the graph, intercepts our
 *      shaped interrupt, POSTs the task to the awaithumans server,
 *      long-polls until terminal, and resumes the graph with
 *      `Command({ resume: response })` until the graph completes.
 *
 * @example Node-side
 * ```ts
 * import { awaitHuman } from "awaithumans/langgraph";
 * import { z } from "zod";
 *
 * const ReviewSchema = z.object({ approved: z.boolean() });
 *
 * function reviewNode(state: { amount: number }) {
 *   const decision = awaitHuman({
 *     task: "Approve refund?",
 *     payloadSchema: z.object({ amount: z.number() }),
 *     payload: { amount: state.amount },
 *     responseSchema: ReviewSchema,
 *     timeoutMs: 15 * 60 * 1000,
 *   });
 *   return { approved: decision.approved };
 * }
 * ```
 *
 * @example Driver-side
 * ```ts
 * import { driveHumanLoop } from "awaithumans/langgraph";
 *
 * const finalState = await driveHumanLoop({
 *   graph: compiledGraph,
 *   inputState: { amount: 250 },
 *   config: { configurable: { thread_id: "wf-1" } },
 *   serverUrl: "http://localhost:3001",
 *   apiKey: process.env.AWAITHUMANS_ADMIN_API_TOKEN,
 * });
 * ```
 *
 * Requires:
 *   npm install @langchain/langgraph
 *   (peer dependency — declared as optional in this SDK so the base
 *    install doesn't pull in LangGraph for users who don't need it.)
 */

import type { ZodType } from "zod";
import { zodToJsonSchema } from "zod-to-json-schema";

import { POLL_INTERVAL_SECONDS } from "../../constants";
import {
	PollError,
	SchemaValidationError,
	TaskCancelledError,
	TaskCreateError,
	TaskTimeoutError,
	VerificationExhaustedError,
} from "../../errors";
import { generateIdempotencyKey } from "../../idempotency";
import type { AssignTo, AwaitHumanOptions, VerifierConfig } from "../../types";
import { serializeAssignTo } from "../../wire";

// Magic key the driver pattern-matches on. Other interrupts in the
// graph (operator confirmations, branching decisions) won't have
// this key, so the driver can ignore them.
const INTERRUPT_KEY = "awaithumans";

// ─── Node-side: awaitHuman ──────────────────────────────────────────

interface AwaithumansDescriptor {
	task: string;
	payload: unknown;
	payload_schema: unknown;
	response_schema: unknown;
	timeout_seconds: number;
	idempotency_key: string;
	assign_to: ReturnType<typeof serializeAssignTo>;
	notify: string[] | null;
	verifier_config: VerifierConfig | null;
	redact_payload: boolean;
}

/**
 * Suspend a LangGraph node until a human completes the task.
 *
 * Synchronous (matches LangGraph's node API). On first execution,
 * `interrupt(...)` raises `GraphInterrupt` and the graph parks. On
 * resume, this function validates the response against
 * `responseSchema` and returns a typed value.
 *
 * Re-entry semantics: the LangGraph runtime re-executes the whole
 * node on resume. Side effects BEFORE this call run twice. Move
 * them after `awaitHuman` or wrap them in idempotency.
 */
export async function awaitHuman<TPayload, TResponse>(
	options: AwaitHumanOptions<TPayload, TResponse>,
): Promise<TResponse> {
	const lg = await loadLangGraph();

	const idempotencyKey =
		options.idempotencyKey ??
		`langgraph:${(await generateIdempotencyKey(options.task, options.payload)).slice(
			0,
			32,
		)}`;

	const descriptor: AwaithumansDescriptor = {
		task: options.task,
		payload: options.payload,
		payload_schema: zodToJsonSchema(options.payloadSchema),
		response_schema: zodToJsonSchema(options.responseSchema),
		timeout_seconds: Math.round(options.timeoutMs / 1000),
		idempotency_key: idempotencyKey,
		assign_to: serializeAssignTo(options.assignTo as AssignTo | undefined),
		notify: options.notify ?? null,
		verifier_config:
			(options.verifier as VerifierConfig | undefined) ?? null,
		redact_payload: options.redactPayload ?? false,
	};

	// `interrupt` raises on first call (caught by the LangGraph
	// runtime), returns the resume value on second call. We wrap our
	// descriptor under the magic key so the driver can pattern-match.
	const rawResponse = lg.interrupt({ [INTERRUPT_KEY]: descriptor });

	const validated = options.responseSchema.safeParse(rawResponse);
	if (!validated.success) {
		throw new SchemaValidationError("response", validated.error.message);
	}
	return validated.data;
}

// ─── Driver-side: driveHumanLoop ────────────────────────────────────

export interface DriveHumanLoopOptions {
	/** Compiled LangGraph (the result of `graphBuilder.compile(...)`). */
	graph: LangGraphLike;

	/** Initial state to stream into the graph. */
	inputState: unknown;

	/**
	 * LangGraph config — typically `{ configurable: { thread_id: "..." } }`.
	 * Required for graphs with checkpointers.
	 */
	config: Record<string, unknown>;

	/** awaithumans server base URL, e.g. `http://localhost:3001`. */
	serverUrl: string;

	/** Bearer token for `serverUrl`. */
	apiKey?: string;

	/** Long-poll reconnection interval. Defaults to the SDK constant. */
	pollIntervalSeconds?: number;
}

/**
 * Run a graph until it completes, handling awaithumans interrupts.
 *
 * Streams the graph, intercepts interrupts whose payload has the
 * `awaithumans` key, creates the task on the awaithumans server,
 * long-polls until terminal, and resumes the graph with
 * `Command({ resume: response })`. Returns the graph's final state.
 *
 * Other interrupts (graph-domain interrupts the user raises for
 * non-awaithumans reasons) re-raise — pass them up to the caller.
 *
 * Polling-based by design — durability comes from LangGraph's
 * checkpointer, not from us. Webhook-driven resume is a planned
 * post-launch follow-up.
 */
export async function driveHumanLoop(
	options: DriveHumanLoopOptions,
): Promise<unknown> {
	const lg = await loadLangGraph();
	const pollSeconds = options.pollIntervalSeconds ?? POLL_INTERVAL_SECONDS;

	let currentInput: unknown = options.inputState;

	while (true) {
		const descriptor = await streamUntilInterrupt(
			options.graph,
			currentInput,
			options.config,
		);
		if (descriptor === null) {
			// Graph completed — return the final state.
			const state = await getState(options.graph, options.config);
			return state;
		}

		const response = await waitForHuman({
			descriptor,
			serverUrl: options.serverUrl,
			apiKey: options.apiKey,
			pollIntervalSeconds: pollSeconds,
		});

		currentInput = lg.Command({ resume: response });
	}
}

async function streamUntilInterrupt(
	graph: LangGraphLike,
	inputState: unknown,
	config: Record<string, unknown>,
): Promise<AwaithumansDescriptor | null> {
	// LangGraph's stream yields chunks per node update. Interrupts
	// surface as a `__interrupt__` key on the chunk.
	for await (const chunk of graph.stream(inputState, {
		...config,
		streamMode: "updates",
	})) {
		if (chunk && typeof chunk === "object" && "__interrupt__" in chunk) {
			const descriptor = extractDescriptor(
				(chunk as Record<string, unknown>).__interrupt__,
			);
			if (descriptor !== null) return descriptor;
		}
	}

	// Graph stream ended. Check state for any pending interrupt that
	// wasn't surfaced via the chunk stream (LangGraph version
	// differences — both shapes need to work).
	const state = await getState(graph, config);
	const interrupts = (state as { interrupts?: unknown[] }).interrupts ?? [];
	for (const itr of interrupts) {
		const value = (itr as { value?: unknown }).value ?? itr;
		const descriptor = extractDescriptor(value);
		if (descriptor !== null) return descriptor;
	}

	return null;
}

/**
 * Walk a value (dict, list of Interrupt objects, etc.) looking for
 * the awaithumans descriptor. Returns null when none found — the
 * caller passes the interrupt through to user code.
 */
export function extractDescriptor(value: unknown): AwaithumansDescriptor | null {
	if (value && typeof value === "object" && !Array.isArray(value)) {
		const obj = value as Record<string, unknown>;
		if (INTERRUPT_KEY in obj) {
			const sub = obj[INTERRUPT_KEY];
			return isDescriptor(sub) ? sub : null;
		}
	}
	if (Array.isArray(value)) {
		for (const item of value) {
			const inner = (item as { value?: unknown })?.value ?? item;
			const found = extractDescriptor(inner);
			if (found !== null) return found;
		}
	}
	return null;
}

function isDescriptor(value: unknown): value is AwaithumansDescriptor {
	return (
		typeof value === "object" &&
		value !== null &&
		"task" in value &&
		"timeout_seconds" in value
	);
}

async function getState(
	graph: LangGraphLike,
	config: Record<string, unknown>,
): Promise<unknown> {
	// Different versions expose either `getState` (sync) or
	// `aGetState` (async). Tolerate both.
	const method =
		(graph as { aGetState?: typeof graph.getState }).aGetState ??
		graph.getState;
	const result = method.call(graph, config);
	return result instanceof Promise ? await result : result;
}

// ─── HTTP: create task + long-poll ──────────────────────────────────

interface WaitForHumanOptions {
	descriptor: AwaithumansDescriptor;
	serverUrl: string;
	apiKey: string | undefined;
	pollIntervalSeconds: number;
}

async function waitForHuman(opts: WaitForHumanOptions): Promise<unknown> {
	const headers: Record<string, string> = {
		"Content-Type": "application/json",
	};
	if (opts.apiKey) headers["Authorization"] = `Bearer ${opts.apiKey}`;

	const base = opts.serverUrl.replace(/\/$/, "");
	const body = {
		task: opts.descriptor.task,
		payload: opts.descriptor.payload,
		payload_schema: opts.descriptor.payload_schema,
		response_schema: opts.descriptor.response_schema,
		form_definition: null,
		timeout_seconds: opts.descriptor.timeout_seconds,
		idempotency_key: opts.descriptor.idempotency_key,
		assign_to: opts.descriptor.assign_to,
		notify: opts.descriptor.notify,
		verifier_config: opts.descriptor.verifier_config,
		redact_payload: opts.descriptor.redact_payload,
		callback_url: null,
	};

	const createResp = await fetch(`${base}/api/tasks`, {
		method: "POST",
		headers,
		body: JSON.stringify(body),
	});
	if (createResp.status !== 200 && createResp.status !== 201) {
		throw new TaskCreateError(createResp.status, await safeBodyText(createResp));
	}
	const taskId = ((await createResp.json()) as { id: string }).id;

	return await pollUntilTerminal({
		base,
		headers,
		taskId,
		taskDescription: opts.descriptor.task,
		timeoutSeconds: opts.descriptor.timeout_seconds,
		pollIntervalSeconds: opts.pollIntervalSeconds,
	});
}

interface PollOptions {
	base: string;
	headers: Record<string, string>;
	taskId: string;
	taskDescription: string;
	timeoutSeconds: number;
	pollIntervalSeconds: number;
}

async function pollUntilTerminal(opts: PollOptions): Promise<unknown> {
	while (true) {
		const url = `${opts.base}/api/tasks/${encodeURIComponent(
			opts.taskId,
		)}/poll?timeout=${opts.pollIntervalSeconds}`;
		const resp = await fetch(url, { headers: opts.headers });
		if (resp.status !== 200) {
			throw new PollError(opts.taskId, resp.status, await safeBodyText(resp));
		}
		const poll = (await resp.json()) as {
			status: string;
			response: unknown;
			verification_attempt?: number;
		};
		switch (poll.status) {
			case "completed":
				return poll.response;
			case "timed_out":
				throw new TaskTimeoutError(opts.taskDescription, opts.timeoutSeconds * 1000);
			case "cancelled":
				throw new TaskCancelledError(opts.taskDescription);
			case "verification_exhausted":
				throw new VerificationExhaustedError(
					opts.taskDescription,
					poll.verification_attempt ?? 0,
				);
			default:
				// Server's long-poll just hit its own ~25s timeout; reconnect.
				continue;
		}
	}
}

async function safeBodyText(resp: Response): Promise<string> {
	try {
		return await resp.text();
	} catch {
		return "(body unavailable)";
	}
}

// ─── Lazy peer-dep loader ───────────────────────────────────────────

interface LangGraphLike {
	stream(input: unknown, config: Record<string, unknown>): AsyncIterable<unknown>;
	getState(config: Record<string, unknown>): unknown;
}

interface LangGraphApi {
	interrupt(value: unknown): unknown;
	Command(args: { resume: unknown }): unknown;
}

let cachedApi: LangGraphApi | null = null;

async function loadLangGraph(): Promise<LangGraphApi> {
	if (cachedApi !== null) return cachedApi;
	try {
		const moduleName = "@langchain/langgraph";
		const mod = (await import(/* @vite-ignore */ moduleName)) as unknown as LangGraphApi;
		cachedApi = mod;
		return mod;
	} catch (cause) {
		throw new Error(
			"The LangGraph adapter requires `@langchain/langgraph`.\n" +
				"Install with: npm install @langchain/langgraph\n" +
				`Underlying error: ${(cause as Error).message}`,
		);
	}
}
