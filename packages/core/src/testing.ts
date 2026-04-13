/**
 * Test client for awaithumans.
 *
 * Runs an in-memory server — no Docker, no SQLite, no network.
 * Use in your test suite to simulate the full HITL flow.
 *
 * @example
 * ```ts
 * import { createTestClient } from "awaithumans/testing";
 *
 * const { awaitHuman, completeTask, rejectTask } = createTestClient();
 *
 * test("KYC approval flow", async () => {
 *   const taskPromise = awaitHuman({
 *     task: "Approve KYC",
 *     payloadSchema: KYCPayload,
 *     payload: testKYC,
 *     responseSchema: KYCResponse,
 *     timeoutMs: 60_000,
 *   });
 *
 *   await completeTask({ approved: true, reason: "ID matches" });
 *   const result = await taskPromise;
 *   expect(result.approved).toBe(true);
 * });
 * ```
 */
export function createTestClient() {
	// TODO: implement in-memory task store + immediate resolution
	// This is a high-priority deliverable — tests depend on it.

	return {
		awaitHuman: async () => {
			throw new Error("Test client not yet implemented");
		},
		completeTask: async (_response: unknown) => {
			throw new Error("Test client not yet implemented");
		},
		rejectTask: async (_reason: string) => {
			throw new Error("Test client not yet implemented");
		},
	};
}
