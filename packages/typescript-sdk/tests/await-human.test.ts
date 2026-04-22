/**
 * Unit tests for `awaitHuman` — covers the wire protocol round-trip
 * against a stubbed `fetch`, every terminal status branch, the
 * validation gates (timeout range, payload schema, marketplace), and
 * the ServerUnreachable path when the network itself fails.
 *
 * Deliberately no real HTTP — the server is Python and has its own
 * integration tests. What we care about here is that the SDK speaks
 * the wire format the server expects and maps every response to the
 * right SDK-level behaviour.
 */

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { z } from "zod";

import { awaitHuman } from "../src/await-human";
import {
	MarketplaceNotAvailableError,
	PollError,
	SchemaValidationError,
	ServerUnreachableError,
	TaskCancelledError,
	TaskCreateError,
	TaskNotFoundError,
	TaskTimeoutError,
	TimeoutRangeError,
	VerificationExhaustedError,
} from "../src/errors";

// ─── Fixtures ────────────────────────────────────────────────────────

const payloadSchema = z.object({ amount: z.number() });
const responseSchema = z.object({ approved: z.boolean() });

const BASE_OPTIONS = {
	task: "Approve wire",
	payloadSchema,
	payload: { amount: 50000 },
	responseSchema,
	timeoutMs: 60_000,
	serverUrl: "http://test.local",
};

// ─── Fetch stub ─────────────────────────────────────────────────────

/**
 * Minimal Response-like object. The SDK only calls `.json()`, `.text()`,
 * and reads `.status` — no need to touch `globalThis.Response`.
 */
function makeResponse(status: number, body: unknown): Response {
	return {
		status,
		json: async () => body,
		text: async () => (typeof body === "string" ? body : JSON.stringify(body)),
	} as unknown as Response;
}

type FetchMock = ReturnType<typeof vi.fn>;

function installFetchSequence(responses: Response[]): FetchMock {
	const fetchMock = vi.fn();
	for (const r of responses) {
		fetchMock.mockResolvedValueOnce(r);
	}
	globalThis.fetch = fetchMock as unknown as typeof fetch;
	return fetchMock;
}

function installFetchReject(err: Error): FetchMock {
	const fetchMock = vi.fn().mockRejectedValue(err);
	globalThis.fetch = fetchMock as unknown as typeof fetch;
	return fetchMock;
}

beforeEach(() => {
	vi.useRealTimers();
});

afterEach(() => {
	vi.restoreAllMocks();
});

// ─── Validation gates ────────────────────────────────────────────────

describe("input validation", () => {
	it("rejects timeoutMs below 1 minute", async () => {
		await expect(
			awaitHuman({ ...BASE_OPTIONS, timeoutMs: 30_000 }),
		).rejects.toBeInstanceOf(TimeoutRangeError);
	});

	it("rejects timeoutMs above 30 days", async () => {
		await expect(
			awaitHuman({ ...BASE_OPTIONS, timeoutMs: 10_000_000_000 }),
		).rejects.toBeInstanceOf(TimeoutRangeError);
	});

	it("rejects payload that doesn't match the schema", async () => {
		await expect(
			awaitHuman({
				...BASE_OPTIONS,
				// `amount` must be a number; we send a string.
				payload: { amount: "not-a-number" } as unknown as { amount: number },
			}),
		).rejects.toBeInstanceOf(SchemaValidationError);
	});

	it("rejects reserved marketplace assignment", async () => {
		await expect(
			awaitHuman({ ...BASE_OPTIONS, assignTo: { marketplace: true } }),
		).rejects.toBeInstanceOf(MarketplaceNotAvailableError);
	});
});

// ─── Happy path ──────────────────────────────────────────────────────

describe("happy path", () => {
	it("POSTs a well-formed create body and returns the validated response", async () => {
		const fetchMock = installFetchSequence([
			makeResponse(200, { id: "task-1", status: "created" }),
			makeResponse(200, { status: "completed", response: { approved: true } }),
		]);

		const result = await awaitHuman(BASE_OPTIONS);
		expect(result).toEqual({ approved: true });

		// First call: POST /api/tasks with a snake_case wire body.
		const [createUrl, createInit] = fetchMock.mock.calls[0];
		expect(createUrl).toBe("http://test.local/api/tasks");
		expect(createInit.method).toBe("POST");
		const body = JSON.parse(createInit.body);
		expect(body).toMatchObject({
			task: "Approve wire",
			payload: { amount: 50000 },
			timeout_seconds: 60,
			redact_payload: false,
			callback_url: null,
			form_definition: null,
		});
		expect(typeof body.idempotency_key).toBe("string");
		expect(body.payload_schema).toBeDefined();
		expect(body.response_schema).toBeDefined();

		// Second call: poll.
		const [pollUrl] = fetchMock.mock.calls[1];
		expect(pollUrl).toMatch(
			/^http:\/\/test\.local\/api\/tasks\/task-1\/poll\?timeout=/,
		);
	});

	it("reconnects on non-terminal poll responses", async () => {
		const fetchMock = installFetchSequence([
			makeResponse(200, { id: "task-1", status: "created" }),
			// Server's long-poll times out with task still in flight.
			makeResponse(200, { status: "in_progress", response: null }),
			makeResponse(200, { status: "assigned", response: null }),
			makeResponse(200, { status: "completed", response: { approved: false } }),
		]);

		const result = await awaitHuman(BASE_OPTIONS);
		expect(result).toEqual({ approved: false });
		// Create + 3 polls = 4 total fetch calls.
		expect(fetchMock).toHaveBeenCalledTimes(4);
	});

	it("serializes assignTo: string into { email }", async () => {
		const fetchMock = installFetchSequence([
			makeResponse(200, { id: "t", status: "created" }),
			makeResponse(200, { status: "completed", response: { approved: true } }),
		]);

		await awaitHuman({ ...BASE_OPTIONS, assignTo: "alice@acme.com" });

		const body = JSON.parse(fetchMock.mock.calls[0][1].body);
		expect(body.assign_to).toEqual({ email: "alice@acme.com" });
	});

	it("serializes assignTo: string[] into { emails }", async () => {
		const fetchMock = installFetchSequence([
			makeResponse(200, { id: "t", status: "created" }),
			makeResponse(200, { status: "completed", response: { approved: true } }),
		]);

		await awaitHuman({
			...BASE_OPTIONS,
			assignTo: ["alice@acme.com", "bob@acme.com"],
		});

		const body = JSON.parse(fetchMock.mock.calls[0][1].body);
		expect(body.assign_to).toEqual({
			emails: ["alice@acme.com", "bob@acme.com"],
		});
	});

	it("passes through explicit idempotency key", async () => {
		const fetchMock = installFetchSequence([
			makeResponse(200, { id: "t", status: "created" }),
			makeResponse(200, { status: "completed", response: { approved: true } }),
		]);

		await awaitHuman({ ...BASE_OPTIONS, idempotencyKey: "explicit-key-xyz" });

		const body = JSON.parse(fetchMock.mock.calls[0][1].body);
		expect(body.idempotency_key).toBe("explicit-key-xyz");
	});
});

// ─── Terminal status branches ────────────────────────────────────────

describe("terminal status handling", () => {
	it("throws TaskTimeoutError on status=timed_out", async () => {
		installFetchSequence([
			makeResponse(200, { id: "t", status: "created" }),
			makeResponse(200, { status: "timed_out", response: null }),
		]);
		await expect(awaitHuman(BASE_OPTIONS)).rejects.toBeInstanceOf(
			TaskTimeoutError,
		);
	});

	it("throws TaskCancelledError on status=cancelled", async () => {
		installFetchSequence([
			makeResponse(200, { id: "t", status: "created" }),
			makeResponse(200, { status: "cancelled", response: null }),
		]);
		await expect(awaitHuman(BASE_OPTIONS)).rejects.toBeInstanceOf(
			TaskCancelledError,
		);
	});

	it("throws VerificationExhaustedError on status=verification_exhausted", async () => {
		installFetchSequence([
			makeResponse(200, { id: "t", status: "created" }),
			makeResponse(200, {
				status: "verification_exhausted",
				response: null,
				verification_attempt: 3,
			}),
		]);
		await expect(awaitHuman(BASE_OPTIONS)).rejects.toBeInstanceOf(
			VerificationExhaustedError,
		);
	});

	it("throws SchemaValidationError when response doesn't match responseSchema", async () => {
		installFetchSequence([
			makeResponse(200, { id: "t", status: "created" }),
			// Server claims completion but the response doesn't satisfy our schema.
			makeResponse(200, { status: "completed", response: { approved: "yes" } }),
		]);
		await expect(awaitHuman(BASE_OPTIONS)).rejects.toBeInstanceOf(
			SchemaValidationError,
		);
	});
});

// ─── Transport errors ────────────────────────────────────────────────

describe("transport errors", () => {
	it("throws TaskCreateError on non-2xx from POST /api/tasks", async () => {
		installFetchSequence([makeResponse(503, "service unavailable")]);
		await expect(awaitHuman(BASE_OPTIONS)).rejects.toBeInstanceOf(
			TaskCreateError,
		);
	});

	it("throws TaskNotFoundError on 404 from poll", async () => {
		installFetchSequence([
			makeResponse(200, { id: "t", status: "created" }),
			makeResponse(404, "not found"),
		]);
		await expect(awaitHuman(BASE_OPTIONS)).rejects.toBeInstanceOf(
			TaskNotFoundError,
		);
	});

	it("throws PollError on non-200/404 from poll", async () => {
		installFetchSequence([
			makeResponse(200, { id: "t", status: "created" }),
			makeResponse(500, "internal error"),
		]);
		await expect(awaitHuman(BASE_OPTIONS)).rejects.toBeInstanceOf(PollError);
	});

	it("throws ServerUnreachableError when fetch itself rejects", async () => {
		installFetchReject(new Error("ECONNREFUSED"));
		await expect(awaitHuman(BASE_OPTIONS)).rejects.toBeInstanceOf(
			ServerUnreachableError,
		);
	});
});

// ─── Server URL resolution ──────────────────────────────────────────

describe("server URL resolution", () => {
	it("trims trailing slash from explicit serverUrl", async () => {
		const fetchMock = installFetchSequence([
			makeResponse(200, { id: "t", status: "created" }),
			makeResponse(200, { status: "completed", response: { approved: true } }),
		]);

		await awaitHuman({ ...BASE_OPTIONS, serverUrl: "http://test.local/" });

		expect(fetchMock.mock.calls[0][0]).toBe("http://test.local/api/tasks");
	});
});
