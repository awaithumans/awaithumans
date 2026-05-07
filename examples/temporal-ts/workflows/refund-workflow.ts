/**
 * Temporal workflow that pauses for a human approval through awaithumans.
 *
 * Mirrors the Python `refund_workflow.py`:
 *
 *   1. `awaitHuman()` from the temporal adapter parks the workflow
 *      until either a signal (carrying the human's response) arrives
 *      or the timeout fires.
 *   2. On approval, the workflow calls a downstream activity to
 *      "actually move the money" — a stand-in for your payments
 *      provider call.
 *   3. On rejection, the workflow ends with an outcome record.
 *   4. On timeout, the SDK throws `TaskTimeoutError` so the operator's
 *      monitoring sees the abandoned approval.
 *
 * Determinism: the workflow file is loaded inside Temporal's sandbox.
 * Anything non-deterministic (process.env, fs, network, randomness)
 * happens via:
 *   - The temporal adapter's activity that POSTs the task at start
 *   - The downstream `processRefund` activity
 *   - The kickoff script that injects callback URL + API key as
 *     workflow inputs
 *
 * The workflow itself only orchestrates.
 */

import { proxyActivities, workflowInfo } from "@temporalio/workflow";
import { awaitHuman } from "awaithumans/temporal";
import { z } from "zod";

import type { ProcessRefundInput } from "../activities/process-refund.js";

// ─── Activity proxy ────────────────────────────────────────────────────

const { processRefund } = proxyActivities<{
	processRefund(input: ProcessRefundInput): Promise<string>;
}>({
	startToCloseTimeout: "30 seconds",
});

// ─── Schemas the human sees / sends ───────────────────────────────────

const RefundPayload = z.object({
	amountUsd: z.number(),
	customerId: z.string(),
	reason: z.string(),
});

const RefundDecision = z.object({
	approved: z.boolean().describe("Approve this refund?"),
	notes: z.string().optional(),
});

// ─── Workflow input ────────────────────────────────────────────────────

export interface RefundWorkflowInput {
	amountUsd: number;
	customerId: string;
	/** Where the awaithumans server can reach the callback receiver. */
	callbackBase: string;
	/** awaithumans server URL (so the activity knows where to POST). */
	serverUrl: string;
	/**
	 * Bearer token for the awaithumans server. Threaded as input rather
	 * than read from env because the workflow sandbox doesn't see
	 * `process.env`. Real deployments inject this from the kickoff
	 * caller (a web server / CLI / scheduler that DOES have env).
	 */
	apiKey: string;
}

export interface RefundWorkflowResult {
	refundId: string | null;
	outcome: "approved" | "rejected";
	notes: string | null;
}

// ─── Workflow ──────────────────────────────────────────────────────────

export async function refundWorkflow(
	input: RefundWorkflowInput,
): Promise<RefundWorkflowResult> {
	const { workflowId } = workflowInfo();
	const callbackUrl = `${input.callbackBase.replace(/\/$/, "")}/awaithumans/callback?wf=${workflowId}`;

	const decision = await awaitHuman({
		task: `Approve $${input.amountUsd} refund for ${input.customerId}?`,
		payloadSchema: RefundPayload,
		payload: {
			amountUsd: input.amountUsd,
			customerId: input.customerId,
			reason: "Customer reports duplicate charge.",
		},
		responseSchema: RefundDecision,
		// 15-minute window — plenty of time for a human review during
		// business hours, short enough that abandoned tasks surface
		// in monitoring before the day is out.
		timeoutMs: 15 * 60 * 1000,
		callbackUrl,
		serverUrl: input.serverUrl,
		apiKey: input.apiKey,
	});

	if (!decision.approved) {
		return {
			refundId: null,
			outcome: "rejected",
			notes: decision.notes ?? null,
		};
	}

	const refundId = await processRefund({
		customerId: input.customerId,
		amountUsd: input.amountUsd,
		decisionNotes: decision.notes ?? null,
	});

	return {
		refundId,
		outcome: "approved",
		notes: decision.notes ?? null,
	};
}
