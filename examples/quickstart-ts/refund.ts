/**
 * awaithumans quickstart (TypeScript) — delegate a refund approval to a human.
 *
 * Prerequisite (in another terminal):
 *     npx awaithumans dev
 *
 * Then in this terminal:
 *     npm install
 *     npm start
 *
 * What happens:
 *     1. This script creates a task on the server and awaits until
 *        a human completes it.
 *     2. Open http://localhost:3001 — the task shows up in the queue
 *        with an approve/reject form.
 *     3. Submit your decision. This script receives the typed response
 *        and prints it. That's it.
 */

import { z } from "zod";
import { awaitHuman } from "awaithumans";

// Data the human sees while reviewing.
const RefundRequest = z.object({
	orderId: z.string(),
	customer: z.string(),
	amountUsd: z.number(),
	reason: z.string(),
});

// Structured response the human fills out. `approved` drives a toggle;
// `reason` renders as a short-answer text field.
const Decision = z.object({
	approved: z.boolean().describe("Approve the refund?"),
	reason: z.string().describe("Why did you approve / reject? Short answer."),
});

async function main(): Promise<void> {
	console.log("→ creating task on the awaithumans server...");
	console.log("  Open http://localhost:3001 to review.\n");

	const orderId = "A-4721";

	const decision = await awaitHuman({
		task: "Approve refund request",
		payloadSchema: RefundRequest,
		payload: {
			orderId,
			customer: "jane@example.com",
			amountUsd: 180.0,
			reason: "Item arrived damaged",
		},
		responseSchema: Decision,
		timeoutMs: 900_000, // 15 minutes — plenty of time to walk to the kitchen
		// Ties this call to the order. Same key, same task — forever.
		// If the agent crashes mid-call and the human approves during
		// the outage, re-running with the same key returns the stored
		// decision (the `if (decision.approved)` block runs as if
		// nothing happened). Without an explicit key the SDK
		// auto-hashes (task, payload) — fine for dev, but tie to your
		// real business event (orderId, transferId, requestId) in
		// production. To start a fresh review for the same event
		// (e.g. yesterday's task timed out), use a distinct key like
		// `refund:${orderId}:retry-1`.
		idempotencyKey: `refund:${orderId}`,
	});

	if (decision.approved) {
		console.log(`✓ Refund approved. Reason: ${decision.reason}`);
	} else {
		console.log(`✗ Refund rejected. Reason: ${decision.reason}`);
	}
}

main().catch((err) => {
	console.error(err);
	process.exit(1);
});
