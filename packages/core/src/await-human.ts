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
		options.idempotencyKey ?? generateIdempotencyKey(options.task, options.payload);

	// ── Convert schemas to JSON Schema for the wire ─────────────────────
	const payloadJsonSchema = zodToJsonSchema(options.payloadSchema);
	const responseJsonSchema = zodToJsonSchema(options.responseSchema);

	// ── Create task on the server ───────────────────────────────────────
	// TODO: implement HTTP client to server
	// POST /api/tasks { task, payload, payloadSchema, responseSchema, timeoutMs, assignTo, notify, idempotencyKey, redactPayload }

	// ── Long-poll until completion or timeout ───────────────────────────
	// TODO: implement long-poll loop with reconnection every ~25s
	// GET /api/tasks/:id/poll

	// ── Validate response against schema ────────────────────────────────
	// TODO: parse and validate the response, return typed result

	throw new Error("Not yet implemented — core SDK is being built.");
}
