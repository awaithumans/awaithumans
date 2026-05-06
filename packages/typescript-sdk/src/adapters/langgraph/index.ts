/**
 * LangGraph adapter — interrupt/resume durable HITL.
 *
 * @example
 * ```ts
 * import { awaitHuman } from "awaithumans/langgraph";
 *
 * // Inside a LangGraph node:
 * const result = await awaitHuman({
 *   task: "Approve this KYC?",
 *   payloadSchema: KYCPayload,
 *   payload: kycData,
 *   responseSchema: KYCResponse,
 *   timeoutMs: 15 * 60 * 1000,
 * });
 * ```
 *
 * Requires: npm install @langchain/langgraph
 */

import type { AwaitHumanOptions } from "../../types/index.js";

/**
 * LangGraph-durable version of awaitHuman.
 *
 * Uses LangGraph interrupt/resume with checkpoint-based durability.
 */
export async function awaitHuman<TPayload, TResponse>(
	options: AwaitHumanOptions<TPayload, TResponse>,
): Promise<TResponse> {
	// TODO: implement
	// 1. Create task on the awaithumans server (HTTP POST)
	// 2. Use langgraph interrupt(taskId) to suspend the graph
	// 3. Server fires webhook on completion → callback handler resumes graph
	// 4. Validate response against responseSchema, return typed result
	// Idempotency key: threadId + nodeId from checkpoint
	throw new Error("LangGraph adapter not yet implemented.");
}

/**
 * Pre-built callback handler for resuming a LangGraph graph.
 *
 * @example
 * ```ts
 * import { createLangGraphCallbackHandler } from "awaithumans/langgraph";
 *
 * app.post("/awaithumans/callback", createLangGraphCallbackHandler(graphClient));
 * ```
 */
export function createLangGraphCallbackHandler(_graphClient: unknown): unknown {
	// TODO: implement
	throw new Error("LangGraph callback handler not yet implemented.");
}
