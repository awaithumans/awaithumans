/**
 * Tests for the TypeScript LangGraph adapter.
 *
 * Two surfaces:
 *
 *   - **Descriptor extraction** — the driver pattern-matches on the
 *     awaithumans key. Other interrupts (operator confirmations,
 *     branching decisions) must NOT be consumed.
 *   - **driveHumanLoop / waitForHuman** wire path — POSTs the
 *     create-task body, long-polls, maps each terminal status to
 *     the right typed error. Tested with stubbed `fetch`.
 *
 * Not tested here: the workflow-side `awaitHuman()` against a real
 * LangGraph runtime. That requires a checkpointer + compiled graph
 * (covered in the Python adapter's manual smoke test). The
 * descriptor-shape contract that the Python smoke test verifies is
 * pinned cross-language by `extractDescriptor` + `awaitHuman`'s
 * call-site contract.
 */

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { z } from "zod";

// Hoisted mock — the adapter dynamically imports `@langchain/langgraph`,
// which isn't installed in CI. We replace the entire module surface
// with the two functions the adapter actually calls. Each test sets
// the `interrupt` return value to script the resume payload.
const mockInterrupt = vi.fn();
vi.mock("@langchain/langgraph", () => ({
	interrupt: (value: unknown) => mockInterrupt(value),
	Command: ({ resume }: { resume: unknown }) => ({ __command: true, resume }),
}));

import {
	awaitHuman,
	driveHumanLoop,
	extractDescriptor,
} from "../src/adapters/langgraph/index";
import {
	SchemaValidationError,
	TaskCancelledError,
	TaskCreateError,
	TaskTimeoutError,
	VerificationExhaustedError,
} from "../src/errors";

// ─── extractDescriptor (no peer dep needed) ─────────────────────────

describe("extractDescriptor", () => {
	const validDescriptor = {
		task: "Approve",
		payload: { x: 1 },
		payload_schema: {},
		response_schema: {},
		timeout_seconds: 900,
		idempotency_key: "langgraph:abc",
		assign_to: null,
		notify: null,
		verifier_config: null,
		redact_payload: false,
	};

	it("returns the descriptor when the dict has the awaithumans key", () => {
		expect(extractDescriptor({ awaithumans: validDescriptor })).toEqual(
			validDescriptor,
		);
	});

	it("walks an array of Interrupt-shaped objects", () => {
		// LangGraph's state.interrupts is a list of Interrupt objects;
		// the dict lives at `.value`. Tolerate both shapes.
		const interrupts = [{ value: { awaithumans: validDescriptor } }];
		expect(extractDescriptor(interrupts)).toEqual(validDescriptor);
	});

	it("returns null for non-awaithumans interrupts (driver passes them through)", () => {
		expect(
			extractDescriptor({ operator_confirm: { prompt: "ok?" } }),
		).toBeNull();
		expect(extractDescriptor("plain string")).toBeNull();
		expect(extractDescriptor(null)).toBeNull();
		expect(extractDescriptor(42)).toBeNull();
	});

	it("returns null when the awaithumans value is malformed", () => {
		// Missing required fields → not a real descriptor.
		expect(extractDescriptor({ awaithumans: { notWhatWeWant: 1 } })).toBeNull();
	});
});

// ─── driveHumanLoop wire path ───────────────────────────────────────
//
// We stub the LangGraph peer dep AND `fetch` to drive a deterministic
// scenario: graph yields an awaithumans interrupt → driver POSTs
// task → long-polls → returns response → graph completes.

const realFetch = globalThis.fetch;

afterEach(() => {
	globalThis.fetch = realFetch;
});

interface FakeChunk {
	__interrupt__?: unknown;
}

class FakeGraph {
	private chunksByCall: FakeChunk[][];
	private callIndex = 0;
	public lastInputs: unknown[] = [];
	public state: { interrupts: unknown[]; values: unknown } = {
		interrupts: [],
		values: { final: true },
	};

	constructor(chunksByCall: FakeChunk[][]) {
		this.chunksByCall = chunksByCall;
	}

	async *stream(input: unknown, _config: Record<string, unknown>): AsyncIterable<unknown> {
		this.lastInputs.push(input);
		const chunks = this.chunksByCall[this.callIndex] ?? [];
		this.callIndex++;
		for (const c of chunks) yield c;
	}

	getState(_config: Record<string, unknown>): unknown {
		return this.state;
	}
}

const validDescriptor = {
	task: "Approve",
	payload: { amount: 100 },
	payload_schema: {},
	response_schema: {},
	timeout_seconds: 900,
	idempotency_key: "langgraph:abc",
	assign_to: null,
	notify: null,
	verifier_config: null,
	redact_payload: false,
};

describe("driveHumanLoop", () => {
	beforeEach(() => {
		mockInterrupt.mockReset();
	});

	it("posts the create-task body, polls, resumes with response, completes", async () => {
		// Scripted graph: first stream yields our interrupt, second
		// stream (after resume) yields nothing → completion.
		const graph = new FakeGraph([
			[{ __interrupt__: { awaithumans: validDescriptor } }],
			[],
		]);

		// Stub fetch to script a create-task POST + a completed poll.
		let createBody: Record<string, unknown> | null = null;
		globalThis.fetch = vi.fn(async (input: string | URL | Request, init?: RequestInit) => {
			const url = String(input);
			if (url.endsWith("/api/tasks") && init?.method === "POST") {
				createBody = JSON.parse(String(init.body));
				return new Response(JSON.stringify({ id: "task-1" }), { status: 201 });
			}
			if (url.includes("/poll")) {
				return new Response(
					JSON.stringify({ status: "completed", response: { approved: true } }),
					{ status: 200 },
				);
			}
			return new Response("not found", { status: 404 });
		}) as typeof fetch;

		const finalState = await driveHumanLoop({
			graph: graph as any,
			inputState: { amount: 100 },
			config: { configurable: { thread_id: "test" } },
			serverUrl: "http://test",
			apiKey: "test-bearer",
			pollIntervalSeconds: 1,
		});

		expect(finalState).toEqual({ interrupts: [], values: { final: true } });
		// Wire body must match the awaithumans server's CreateTaskRequest.
		expect(createBody!.idempotency_key).toBe("langgraph:abc");
		expect(createBody!.timeout_seconds).toBe(900);
		// On resume, graph received our Command wrapper.
		expect(graph.lastInputs[1]).toEqual({
			__command: true,
			resume: { approved: true },
		});
	});

	const terminalStatuses: ReadonlyArray<{
		status: string;
		exc: new (...args: any[]) => Error;
	}> = [
		{ status: "cancelled", exc: TaskCancelledError },
		{ status: "timed_out", exc: TaskTimeoutError },
		{ status: "verification_exhausted", exc: VerificationExhaustedError },
	];

	for (const { status, exc } of terminalStatuses) {
		it(`raises ${exc.name} when poll returns ${status}`, async () => {
			const graph = new FakeGraph([
				[{ __interrupt__: { awaithumans: validDescriptor } }],
			]);

			globalThis.fetch = vi.fn(async (input: string | URL | Request) => {
				const url = String(input);
				if (url.endsWith("/api/tasks")) {
					return new Response(JSON.stringify({ id: "t-1" }), { status: 201 });
				}
				return new Response(
					JSON.stringify({
						status,
						response: null,
						verification_attempt: 3,
					}),
					{ status: 200 },
				);
			}) as typeof fetch;

			await expect(
				driveHumanLoop({
					graph: graph as any,
					inputState: { x: 1 },
					config: {},
					serverUrl: "http://test",
					pollIntervalSeconds: 1,
				}),
			).rejects.toBeInstanceOf(exc);
		});
	}

	it("raises TaskCreateError on a 5xx create response", async () => {
		const graph = new FakeGraph([
			[{ __interrupt__: { awaithumans: validDescriptor } }],
		]);

		globalThis.fetch = vi.fn(async () =>
			new Response("boom", { status: 503 }),
		) as typeof fetch;

		await expect(
			driveHumanLoop({
				graph: graph as any,
				inputState: {},
				config: {},
				serverUrl: "http://test",
				pollIntervalSeconds: 1,
			}),
		).rejects.toBeInstanceOf(TaskCreateError);
	});

	it("returns final state when the graph completes without an awaithumans interrupt", async () => {
		// Empty stream, no interrupts on state — graph done.
		const graph = new FakeGraph([[]]);
		graph.state = { interrupts: [], values: { result: "ok" } };

		const final = await driveHumanLoop({
			graph: graph as any,
			inputState: {},
			config: {},
			serverUrl: "http://test",
			pollIntervalSeconds: 1,
		});
		expect(final).toEqual({ interrupts: [], values: { result: "ok" } });
	});
});

// ─── Node-side awaitHuman: validates resume value ───────────────────

describe("awaitHuman (node-side)", () => {
	beforeEach(() => {
		mockInterrupt.mockReset();
	});

	it("validates resume value against responseSchema", async () => {
		mockInterrupt.mockReturnValueOnce({ wrong_field: 1 });
		await expect(
			awaitHuman({
				task: "x",
				payloadSchema: z.object({ amount: z.number() }),
				payload: { amount: 1 },
				responseSchema: z.object({ approved: z.boolean() }),
				timeoutMs: 60_000,
			}),
		).rejects.toBeInstanceOf(SchemaValidationError);
	});

	it("returns the typed value when resume matches schema", async () => {
		mockInterrupt.mockReturnValueOnce({ approved: true });
		const result = await awaitHuman({
			task: "Approve",
			payloadSchema: z.object({ amount: z.number() }),
			payload: { amount: 100 },
			responseSchema: z.object({ approved: z.boolean() }),
			timeoutMs: 60_000,
		});
		expect(result).toEqual({ approved: true });
	});

	it("calls interrupt with the awaithumans descriptor shape", async () => {
		mockInterrupt.mockReturnValueOnce({ approved: false });
		await awaitHuman({
			task: "Approve refund?",
			payloadSchema: z.object({ amount: z.number() }),
			payload: { amount: 250 },
			responseSchema: z.object({ approved: z.boolean() }),
			timeoutMs: 900_000,
		});
		// The driver pattern-matches on this exact wire shape; pin it.
		const calls = mockInterrupt.mock.calls;
		expect(calls).toHaveLength(1);
		const value = calls[0][0] as Record<string, any>;
		expect(value).toHaveProperty("awaithumans");
		expect(value.awaithumans.task).toBe("Approve refund?");
		expect(value.awaithumans.timeout_seconds).toBe(900);
		expect(value.awaithumans.idempotency_key).toMatch(/^langgraph:/);
	});
});
