/**
 * Temporal adapter — signal-based durable HITL.
 *
 * @example
 * ```ts
 * import { awaitHuman } from "awaithumans/temporal";
 *
 * // Inside a Temporal workflow:
 * const result = await awaitHuman({
 *   task: "Approve this KYC?",
 *   payloadSchema: KYCPayload,
 *   payload: kycData,
 *   responseSchema: KYCResponse,
 *   timeoutMs: 15 * 60 * 1000,
 * });
 * ```
 *
 * Requires: npm install @temporalio/client @temporalio/workflow
 */

import type { AwaitHumanOptions } from "../../types";

/**
 * Temporal-durable version of awaitHuman.
 *
 * Uses Temporal signals + sleep race for zero-compute waiting.
 * The adapter extracts the workflow execution identity for idempotency.
 */
export async function awaitHuman<TPayload, TResponse>(
	options: AwaitHumanOptions<TPayload, TResponse>,
): Promise<TResponse> {
	// TODO: implement
	// 1. Create task on the awaithumans server (HTTP POST)
	// 2. Register a Temporal signal handler for `awaithumans:${taskId}`
	// 3. Race: workflow.condition(signalReceived) vs workflow.sleep(timeoutMs)
	// 4. On signal: validate response against responseSchema, return typed result
	// 5. On timeout: throw TimeoutError
	// Idempotency key: workflowInfo().workflowId + activityInfo().activityId + attempt
	throw new Error("Temporal adapter not yet implemented.");
}

/**
 * Pre-built callback handler for the user's API server.
 *
 * Receives the webhook from the awaithumans server when a human completes a task,
 * and sends a Temporal signal to resume the workflow.
 *
 * @example
 * ```ts
 * import { createTemporalCallbackHandler } from "awaithumans/temporal";
 * import { Client } from "@temporalio/client";
 *
 * const temporalClient = new Client({ ... });
 * app.post("/awaithumans/callback", createTemporalCallbackHandler(temporalClient));
 * ```
 */
export function createTemporalCallbackHandler(_temporalClient: unknown): unknown {
	// TODO: implement
	// 1. Verify HMAC signature on the webhook
	// 2. Extract workflowId + taskId from payload
	// 3. Call temporalClient.workflow.signal(workflowId, `awaithumans:${taskId}`, response)
	throw new Error("Temporal callback handler not yet implemented.");
}
