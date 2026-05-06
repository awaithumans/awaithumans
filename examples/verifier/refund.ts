/**
 * awaithumans verifier example (TypeScript) — refund approval gated
 * by an LLM verifier.
 *
 * Scenario: the human's decision must pass an LLM quality check before
 * the agent unblocks. The verifier reads the original request, the
 * decision, and a strict policy, then either passes (→ COMPLETED) or
 * rejects (→ REJECTED, can resubmit; → VERIFICATION_EXHAUSTED after
 * the attempt limit).
 *
 * Prerequisites
 * -------------
 * 1. In another terminal, with `ANTHROPIC_API_KEY` exported in that
 *    shell so the SERVER can call Claude:
 *
 *        export ANTHROPIC_API_KEY=sk-ant-...
 *        npx awaithumans dev
 *
 * 2. Then in this terminal:
 *
 *        npm install
 *        npm start
 *
 * What to do (manual verifier test)
 * ---------------------------------
 * Open http://localhost:3001 and review the task. Try the three paths:
 *
 *   Pass         — approve the refund and write a reason that mentions
 *                  "damage" / "policy" / "evidence". Verifier passes;
 *                  this script unblocks with the typed Decision.
 *
 *   Reject+retry — write a vague reason like "ok". Verifier rejects on
 *                  the first attempt; the dashboard shows the rejection
 *                  reason and lets you resubmit. Up to max_attempts.
 *
 *   Exhaust      — keep submitting bad reasons. After max_attempts the
 *                  task transitions to VERIFICATION_EXHAUSTED (terminal)
 *                  and this script throws VerificationExhaustedError.
 */

import { z } from "zod";
import {
	awaitHuman,
	VerificationExhaustedError,
	type VerifierConfig,
} from "awaithumans";

const RefundRequest = z.object({
	orderId: z.string(),
	customer: z.string(),
	amountUsd: z.number(),
	reason: z.string(),
});

const Decision = z.object({
	approved: z.boolean().describe("Approve the refund?"),
	reason: z
		.string()
		.describe(
			"Why? If approving, mention damage / policy / evidence. " +
				"If rejecting, at least 20 characters explaining why.",
		),
});

const VERIFIER_INSTRUCTIONS = `\
You are a quality gate for refund decisions. Read the original
request (in \`payload\`) and the human's decision (in \`response\`).

PASS only if BOTH hold:
  1. If response.approved is true, response.reason must mention
     at least one of: "damage", "policy", "evidence" (case-insensitive).
  2. If response.approved is false, response.reason must be at least
     20 characters and substantively explain the rejection.

Otherwise REJECT with a short, actionable reason the human will see.
`;

const verifierConfig: VerifierConfig = {
	provider: "claude",
	model: "claude-sonnet-4-20250514",
	instructions: VERIFIER_INSTRUCTIONS,
	maxAttempts: 3,
	apiKeyEnv: "ANTHROPIC_API_KEY",
};

async function main(): Promise<void> {
	const orderId = "A-9921";

	console.log("→ creating refund task with a Claude verifier attached...");
	console.log("  Open http://localhost:3001 to review.\n");

	try {
		const decision = await awaitHuman({
			task: "Approve refund (verified)",
			payloadSchema: RefundRequest,
			payload: {
				orderId,
				customer: "riley@example.com",
				amountUsd: 420.0,
				reason: "Item arrived broken; customer sent two photos.",
			},
			responseSchema: Decision,
			timeoutMs: 900_000,
			verifier: verifierConfig,
			idempotencyKey: `refund-verified:${orderId}`,
		});

		if (decision.approved) {
			console.log(
				`✓ Refund approved (verifier passed). Reason: ${decision.reason}`,
			);
		} else {
			console.log(
				`✗ Refund rejected (verifier passed). Reason: ${decision.reason}`,
			);
		}
	} catch (err) {
		if (err instanceof VerificationExhaustedError) {
			console.log(`✗ ${err.message}`);
			console.log(
				"  The agent is unblocked but the task did not pass review.",
			);
			return;
		}
		throw err;
	}
}

main().catch((err) => {
	console.error(err);
	process.exit(1);
});
