/**
 * Generate a deterministic idempotency key from task + payload.
 *
 * Uses canonical JSON (sorted keys) so {a:1, b:2} and {b:2, a:1}
 * produce the same hash. This is the default for direct mode.
 *
 * Durable adapters override this with the engine's execution identity
 * (e.g., Temporal workflowId + activityId + attempt).
 *
 * Uses Web Crypto API (not node:crypto) for cross-platform compatibility
 * with Node, Bun, Deno, and edge runtimes.
 */
export async function generateIdempotencyKey(task: string, payload: unknown): Promise<string> {
	const canonical = canonicalStringify({ task, payload });
	const encoded = new TextEncoder().encode(canonical);
	const hashBuffer = await crypto.subtle.digest("SHA-256", encoded);
	const hashArray = new Uint8Array(hashBuffer);
	return Array.from(hashArray.slice(0, 16))
		.map((b) => b.toString(16).padStart(2, "0"))
		.join("");
}

/**
 * Canonical JSON stringification with sorted keys.
 * Ensures deterministic output regardless of key insertion order.
 */
function canonicalStringify(value: unknown): string {
	if (value === null || value === undefined) {
		return JSON.stringify(value);
	}

	if (Array.isArray(value)) {
		return `[${value.map(canonicalStringify).join(",")}]`;
	}

	if (typeof value === "object") {
		const obj = value as Record<string, unknown>;
		const sorted = Object.keys(obj)
			.sort()
			.map((key) => `${JSON.stringify(key)}:${canonicalStringify(obj[key])}`)
			.join(",");
		return `{${sorted}}`;
	}

	return JSON.stringify(value);
}
