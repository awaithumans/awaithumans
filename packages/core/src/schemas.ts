import { z } from "zod";

/**
 * Validates the AwaitHumanOptions input at the boundary.
 * Used internally by awaitHuman() before sending to the server.
 */
export const awaitHumanInputSchema = z.object({
	task: z.string().min(1, "task must be a non-empty string"),
	timeoutMs: z
		.number()
		.int("timeoutMs must be an integer")
		.min(60_000, "Minimum timeout is 60,000 ms (1 minute)")
		.max(2_592_000_000, "Maximum timeout is 2,592,000,000 ms (30 days)"),
	notify: z.array(z.string()).optional(),
	idempotencyKey: z.string().optional(),
	redactPayload: z.boolean().optional(),
});
