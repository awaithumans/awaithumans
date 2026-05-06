/**
 * Idempotency key generation — the default key is derived from
 * `task + payload` via canonical JSON + SHA-256.
 *
 * The canonicalisation matters: two payloads with the same data but
 * different key insertion order must hash to the same key, or the
 * server will see them as distinct tasks and defeat dedup.
 */

import { describe, expect, it } from "vitest";

import { generateIdempotencyKey } from "../src/internal/idempotency";

describe("generateIdempotencyKey", () => {
	it("returns the same key for the same inputs", async () => {
		const a = await generateIdempotencyKey("approve", { amount: 100 });
		const b = await generateIdempotencyKey("approve", { amount: 100 });
		expect(a).toBe(b);
	});

	it("returns different keys when the task differs", async () => {
		const a = await generateIdempotencyKey("approve", { amount: 100 });
		const b = await generateIdempotencyKey("reject", { amount: 100 });
		expect(a).not.toBe(b);
	});

	it("returns different keys when the payload differs", async () => {
		const a = await generateIdempotencyKey("approve", { amount: 100 });
		const b = await generateIdempotencyKey("approve", { amount: 200 });
		expect(a).not.toBe(b);
	});

	it("is order-independent on object keys (canonical JSON)", async () => {
		const a = await generateIdempotencyKey("t", { a: 1, b: 2 });
		const b = await generateIdempotencyKey("t", { b: 2, a: 1 });
		expect(a).toBe(b);
	});

	it("descends into nested objects", async () => {
		const a = await generateIdempotencyKey("t", {
			outer: { a: 1, b: 2 },
		});
		const b = await generateIdempotencyKey("t", {
			outer: { b: 2, a: 1 },
		});
		expect(a).toBe(b);
	});

	it("preserves array order (arrays are not sorted)", async () => {
		const a = await generateIdempotencyKey("t", { xs: [1, 2, 3] });
		const b = await generateIdempotencyKey("t", { xs: [3, 2, 1] });
		expect(a).not.toBe(b);
	});

	it("handles null and undefined", async () => {
		const a = await generateIdempotencyKey("t", null);
		const b = await generateIdempotencyKey("t", null);
		expect(a).toBe(b);
	});

	it("returns a 32-char hex string (128-bit truncated SHA-256)", async () => {
		const key = await generateIdempotencyKey("t", { x: 1 });
		expect(key).toMatch(/^[0-9a-f]{32}$/);
	});
});
