import { zodToJsonSchema } from "zod-to-json-schema";
import { MarketplaceNotAvailableError, SchemaValidationError, TimeoutRangeError } from "./errors";
import type { AwaitHumanOptions } from "./types";
import { generateIdempotencyKey } from "./idempotency";

const MIN_TIMEOUT_MS = 60_000; // 1 minute
const MAX_TIMEOUT_MS = 2_592_000_000; // 30 days

/**
 * Delegate a task to a human and await the result.
 *
 * Direct mode: long-polls the server until the human completes or timeout.
 * For durable mode, import from `@awaithumans/temporal` or `@awaithumans/langgraph` instead.
 */
export async function awaitHuman<TPayload, TResponse>(
	options: AwaitHumanOptions<TPayload, TResponse>,
): Promise<TResponse> {
	// ── Validate timeout range ──────────────────────────────────────────
	if (options.timeoutMs < MIN_TIMEOUT_MS || options.timeoutMs > MAX_TIMEOUT_MS) {
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

	// ── Generate idempotency key ────────────────────────────────────────
	const idempotencyKey =
		options.idempotencyKey ?? (await generateIdempotencyKey(options.task, options.payload));

	// ── Convert schemas to JSON Schema for the wire ─────────────────────
	const payloadJsonSchema = zodToJsonSchema(options.payloadSchema);
	const responseJsonSchema = zodToJsonSchema(options.responseSchema);

	// ── Resolve server URL ──────────────────────────────────────────────
	const serverUrl = process.env.AWAITHUMANS_URL ?? "http://localhost:3000";

	// ── Create task on the server ───────────────────────────────────────
	// TODO: POST ${serverUrl}/api/tasks
	// Body: { task, payload, payloadSchema: payloadJsonSchema, responseSchema: responseJsonSchema,
	//         timeoutMs, assignTo, notify, idempotencyKey, redactPayload }
	// Returns: { taskId }

	// ── Long-poll until completion or timeout ───────────────────────────
	// TODO: GET ${serverUrl}/api/tasks/${taskId}/poll
	// Reconnect every ~25s to stay under gateway timeouts.
	// On completion: validate response against responseSchema, return typed result.
	// On timeout: throw TimeoutError.
	// On verification_exhausted: throw VerificationExhaustedError.

	// ── Placeholder until server is built ───────────────────────────────
	void idempotencyKey;
	void payloadJsonSchema;
	void responseJsonSchema;
	void serverUrl;
	throw new Error("Not yet implemented — awaiting server package build.");
}
