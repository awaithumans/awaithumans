import { createHash } from "node:crypto";

/**
 * Generate a deterministic idempotency key from task + payload.
 *
 * Uses canonical JSON (sorted keys) so {a:1, b:2} and {b:2, a:1}
 * produce the same hash. This is the default for direct mode.
 *
 * Durable adapters override this with the engine's execution identity
 * (e.g., Temporal workflowId + activityId + attempt).
 */
export function generateIdempotencyKey(task: string, payload: unknown): string {
	const canonical = canonicalStringify({ task, payload });
	return createHash("sha256").update(canonical).digest("hex").slice(0, 32);
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
		const sorted = Object.keys(value as Record<string, unknown>)
			.sort()
			.map((key) => `${JSON.stringify(key)}:${canonicalStringify((value as Record<string, unknown>)[key])}`)
			.join(",");
		return `{${sorted}}`;
	}

	return JSON.stringify(value);
}
