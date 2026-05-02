/**
 * Tests for the TypeScript Temporal adapter.
 *
 * Three surfaces:
 *
 *   - `signBody` / signature verification — must produce the same
 *     `sha256=<hex>` output as the Python server's HKDF→HMAC chain
 *     so cross-language receivers interoperate.
 *   - `dispatchSignal` — the user-web-server-side helper. Verifies
 *     HMAC, parses body, calls `client.getHandle(...).signal(...)`.
 *     Tested with a fake Temporal client.
 *   - `awaithumansCreateTask` — the activity that POSTs to the
 *     awaithumans server. Tested by stubbing `fetch`.
 *
 * Not tested here: workflow-side `awaitHuman()`. That requires a
 * real Temporal worker harness, which is heavy enough to live in
 * an integration suite (see Python tests for the equivalent).
 * The behaviour the workflow code rides on (signature verify,
 * payload parse, signal routing) IS covered here.
 */

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
	awaithumansCreateTask,
	dispatchSignal,
	signBody,
	type TemporalClientLike,
} from "../src/adapters/temporal/index";

// Same key on both sides — mirrors how operators configure the
// awaithumans server and the user's web server. Must be a valid
// urlsafe-b64-encoded 32-byte value because that's what Python's
// `secrets.token_urlsafe(32)` produces and what `get_key()` decodes.
const TEST_PAYLOAD_KEY = "tlR5UCElY4QIjThpO4TlL1GzTzXrQQJYa3BtvZ0FOBQ";

// Precomputed by the Python `sign_body` helper using TEST_PAYLOAD_KEY
// over `b'{"task":"x"}'`. If this assertion fails after a code change,
// either the HKDF derivation drifted between Python and TS, or the
// HMAC parameters did. Cross-language parity test, basically.
const PYTHON_KNOWN_GOOD_SIGNATURE =
	"sha256=01f15718f6cea5face28432c8075dbde55961458f02a25681ab1531414df6828";

// ─── signBody / verify ───────────────────────────────────────────────

describe("signBody", () => {
	it("produces sha256-prefixed hex output", async () => {
		const sig = await signBody(
			new TextEncoder().encode('{"task":"x"}'),
			TEST_PAYLOAD_KEY,
		);
		expect(sig).toMatch(/^sha256=[0-9a-f]{64}$/);
	});

	it("is deterministic for the same body + key", async () => {
		const body = new TextEncoder().encode("hello");
		const a = await signBody(body, TEST_PAYLOAD_KEY);
		const b = await signBody(body, TEST_PAYLOAD_KEY);
		expect(a).toEqual(b);
	});

	it("changes when the body changes (catches tampering)", async () => {
		const a = await signBody(new TextEncoder().encode("hello"), TEST_PAYLOAD_KEY);
		const b = await signBody(new TextEncoder().encode("hellp"), TEST_PAYLOAD_KEY);
		expect(a).not.toEqual(b);
	});

	it("matches the Python server's signature byte-for-byte (cross-language parity)", async () => {
		// If THIS test fails, a Python receiver will reject every
		// webhook a TS workflow signs (or vice versa). The HKDF
		// derivation parameters must stay locked between Python and TS.
		const sig = await signBody(
			new TextEncoder().encode('{"task":"x"}'),
			TEST_PAYLOAD_KEY,
		);
		expect(sig).toBe(PYTHON_KNOWN_GOOD_SIGNATURE);
	});
});

// ─── dispatchSignal ──────────────────────────────────────────────────

interface SignalCall {
	signal: string;
	arg: unknown;
}

function fakeTemporalClient(): TemporalClientLike & {
	calls: Map<string, SignalCall[]>;
} {
	const calls = new Map<string, SignalCall[]>();
	return {
		calls,
		getHandle(workflowId: string) {
			const sink: SignalCall[] = calls.get(workflowId) ?? [];
			calls.set(workflowId, sink);
			return {
				async signal(name: string, arg: unknown) {
					sink.push({ signal: name, arg });
				},
			};
		},
	};
}

describe("dispatchSignal", () => {
	it("routes signed payload to the correct workflow + signal name", async () => {
		const client = fakeTemporalClient();
		const payload = {
			task_id: "t-1",
			idempotency_key: "temporal:abc123",
			status: "completed",
			response: { approved: true },
		};
		const body = new TextEncoder().encode(JSON.stringify(payload));
		const signature = await signBody(body, TEST_PAYLOAD_KEY);

		await dispatchSignal({
			temporalClient: client,
			workflowId: "wf-42",
			body,
			signatureHeader: signature,
			payloadKey: TEST_PAYLOAD_KEY,
		});

		const calls = client.calls.get("wf-42") ?? [];
		expect(calls).toHaveLength(1);
		expect(calls[0].signal).toBe("awaithumans:temporal:abc123");
		expect(calls[0].arg).toEqual(payload);
	});

	it("rejects a body whose signature is wrong", async () => {
		const client = fakeTemporalClient();
		const body = new TextEncoder().encode('{"idempotency_key":"x","status":"completed"}');

		await expect(
			dispatchSignal({
				temporalClient: client,
				workflowId: "wf-x",
				body,
				signatureHeader: "sha256=" + "0".repeat(64),
				payloadKey: TEST_PAYLOAD_KEY,
			}),
		).rejects.toThrow(/signature/i);
		expect(client.calls.size).toBe(0);
	});

	it("rejects a body without a signature header", async () => {
		const client = fakeTemporalClient();
		const body = new TextEncoder().encode('{"x":1}');
		await expect(
			dispatchSignal({
				temporalClient: client,
				workflowId: "wf-x",
				body,
				signatureHeader: null,
				payloadKey: TEST_PAYLOAD_KEY,
			}),
		).rejects.toThrow();
	});

	it("rejects non-JSON body even with valid signature", async () => {
		const client = fakeTemporalClient();
		const body = new TextEncoder().encode("not-json");
		const signature = await signBody(body, TEST_PAYLOAD_KEY);
		await expect(
			dispatchSignal({
				temporalClient: client,
				workflowId: "wf-x",
				body,
				signatureHeader: signature,
				payloadKey: TEST_PAYLOAD_KEY,
			}),
		).rejects.toThrow(/not JSON/);
	});

	it("rejects body missing idempotency_key", async () => {
		const client = fakeTemporalClient();
		const body = new TextEncoder().encode('{"status":"completed"}');
		const signature = await signBody(body, TEST_PAYLOAD_KEY);
		await expect(
			dispatchSignal({
				temporalClient: client,
				workflowId: "wf-x",
				body,
				signatureHeader: signature,
				payloadKey: TEST_PAYLOAD_KEY,
			}),
		).rejects.toThrow(/idempotency_key/);
	});

	it("accepts signature without the sha256= prefix (some proxies strip it)", async () => {
		const client = fakeTemporalClient();
		const payload = { idempotency_key: "temporal:abc", status: "completed", response: null };
		const body = new TextEncoder().encode(JSON.stringify(payload));
		const sigWithPrefix = await signBody(body, TEST_PAYLOAD_KEY);
		const sigBare = sigWithPrefix.replace("sha256=", "");

		await dispatchSignal({
			temporalClient: client,
			workflowId: "wf-1",
			body,
			signatureHeader: sigBare,
			payloadKey: TEST_PAYLOAD_KEY,
		});
		expect(client.calls.get("wf-1")).toHaveLength(1);
	});
});

// ─── awaithumansCreateTask (the activity) ───────────────────────────

describe("awaithumansCreateTask", () => {
	const realFetch = globalThis.fetch;

	afterEach(() => {
		globalThis.fetch = realFetch;
	});

	it("POSTs to /api/tasks with Bearer auth when apiKey is set", async () => {
		let captured: { url: string; init: RequestInit } | null = null;
		globalThis.fetch = vi.fn(async (url: string | URL | Request, init?: RequestInit) => {
			captured = { url: String(url), init: init ?? {} };
			return new Response(JSON.stringify({ id: "t-from-server", idempotency_key: "k" }), {
				status: 201,
			});
		}) as typeof fetch;

		const out = await awaithumansCreateTask({
			serverUrl: "http://test.local",
			apiKey: "test-bearer",
			body: {
				task: "Approve",
				idempotency_key: "k",
				callback_url: "http://cb.local/cb",
			},
		});

		expect(out).toEqual({ id: "t-from-server", idempotencyKey: "k" });
		expect(captured!.url).toBe("http://test.local/api/tasks");
		expect((captured!.init.headers as Record<string, string>)["Authorization"]).toBe(
			"Bearer test-bearer",
		);
	});

	it("throws when the server returns a 4xx/5xx", async () => {
		globalThis.fetch = vi.fn(async () =>
			new Response("denied", { status: 401 }),
		) as typeof fetch;

		await expect(
			awaithumansCreateTask({
				serverUrl: "http://test.local",
				apiKey: undefined,
				body: { task: "x" },
			}),
		).rejects.toThrow(/HTTP 401/);
	});
});
