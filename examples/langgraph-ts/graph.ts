/**
 * Refund-approval graph — three nodes, one human-in-the-loop interrupt.
 *
 * The shape:
 *
 *     [start] → checkPolicy → (autoApprove) → end
 *                          ↘ humanReview ↗
 *                            (calls awaitHuman)
 *                            (graph pauses here on first run;
 *                             resumes from the same line on Command(resume))
 *
 * `awaitHuman` from `awaithumans/langgraph` is a single line of code
 * inside `humanReviewNode`. When it runs the first time, it POSTs the
 * task to the awaithumans server and then calls LangGraph's
 * `interrupt(...)`. That throws — `graph.invoke()` returns to the
 * caller (our app.ts) with `__interrupt__` populated. The application
 * comes back later (when the webhook fires) with `Command({resume})`,
 * and the SAME line of code now returns the resume value.
 *
 * That's the whole story: one function, two phases, durable in
 * between because LangGraph's checkpointer (the `MemorySaver` we
 * pass at compile time) holds the state.
 */

import {
	Annotation,
	END,
	MemorySaver,
	START,
	StateGraph,
} from "@langchain/langgraph";
import { awaitHuman } from "awaithumans/langgraph";
import { z } from "zod";

// ─── State ──────────────────────────────────────────────────────────

// LangGraph state is a flat object whose keys are merged across nodes.
// The `Annotation` types describe each key: a default value and (for
// reducers) how to combine updates. For this example we just want
// "the latest write wins", which is the default.
export const RefundState = Annotation.Root({
	customerId: Annotation<string>,
	amountUsd: Annotation<number>,
	autoApproved: Annotation<boolean | undefined>,
	approved: Annotation<boolean | undefined>,
	notes: Annotation<string | undefined>,
});

export type RefundStateType = typeof RefundState.State;

// ─── Schemas (shared between adapter call + UI rendering) ───────────

const RefundPayload = z.object({
	customerId: z.string(),
	amountUsd: z.number(),
	reason: z.string(),
});

const RefundResponse = z.object({
	approved: z.boolean(),
	notes: z.string().optional(),
});

// ─── Build-time config the graph nodes need ────────────────────────

export interface BuildGraphOptions {
	awaithumans: {
		serverUrl: string;
		apiKey: string;
		callbackBase: string; // e.g. "http://localhost:8765"
	};
	autoApproveThresholdUsd: number;
}

// ─── Nodes ──────────────────────────────────────────────────────────

function makeCheckPolicy(opts: BuildGraphOptions) {
	return async function checkPolicy(
		state: RefundStateType,
	): Promise<Partial<RefundStateType>> {
		// Trivial policy: refunds under the threshold auto-approve. Real
		// systems would do KYC, fraud-score, etc. — the point is just to
		// show that NOT every path goes through the human.
		const auto = state.amountUsd < opts.autoApproveThresholdUsd;
		console.log(
			`[node:checkPolicy] amount=$${state.amountUsd} threshold=$${opts.autoApproveThresholdUsd} → auto=${auto}`,
		);
		return { autoApproved: auto };
	};
}

function makeHumanReview(opts: BuildGraphOptions, threadId: () => string) {
	return async function humanReview(
		state: RefundStateType,
	): Promise<Partial<RefundStateType>> {
		// Encode the thread id in the callback URL so the webhook
		// handler in app.ts knows which graph instance to resume. The
		// thread id changes per kickoff — we read it from a closure
		// since LangGraph nodes don't have direct access to the
		// runnable config in all node signatures.
		const callbackUrl = `${opts.awaithumans.callbackBase.replace(
			/\/$/,
			"",
		)}/awaithumans/cb?thread=${encodeURIComponent(threadId())}`;

		// THIS is the line. First run: throws GraphInterrupt; graph
		// pauses. Caller catches at .invoke() boundary and returns to
		// the user. On resume (graph re-invoked with Command{resume}),
		// the same line returns the validated decision.
		//
		// `idempotencyKey` includes the thread id so two graph runs
		// with the same payload don't collide on the awaithumans
		// server's per-key uniqueness. Without this, replaying the
		// "$250 refund for cus_demo" demo a second time would get
		// back the FIRST run's task (with its stale callback_url
		// pointing at the previous thread) and the webhook would
		// resume the wrong graph. The default content-hash key is
		// fine for one-off runs but not for HITL across threads.
		const decision = await awaitHuman({
			task: `Approve $${state.amountUsd} refund for ${state.customerId}?`,
			payloadSchema: RefundPayload,
			payload: {
				customerId: state.customerId,
				amountUsd: state.amountUsd,
				reason: "Customer reports duplicate charge.",
			},
			responseSchema: RefundResponse,
			timeoutMs: 15 * 60 * 1000,
			callbackUrl,
			serverUrl: opts.awaithumans.serverUrl,
			apiKey: opts.awaithumans.apiKey,
			idempotencyKey: `langgraph:${threadId()}:humanReview`,
		});

		console.log(
			`[node:humanReview] decision approved=${decision.approved} notes=${
				decision.notes ?? "—"
			}`,
		);
		return {
			approved: decision.approved,
			notes: decision.notes,
		};
	};
}

async function autoApproveNode(
	state: RefundStateType,
): Promise<Partial<RefundStateType>> {
	console.log(`[node:autoApprove] $${state.amountUsd} → approved`);
	return { approved: true, notes: "auto-approved (under threshold)" };
}

// ─── Graph factory ──────────────────────────────────────────────────

/**
 * Build a compiled graph wired to a checkpointer. The `threadIdRef`
 * trick lets the human-review node know which thread it's on without
 * us having to thread the runnable config through node signatures
 * by hand — `app.ts` updates the ref before invoking the graph.
 */
export function buildRefundGraph(
	opts: BuildGraphOptions,
	threadIdRef: { value: string },
): ReturnType<ReturnType<typeof makeBuilder>["compile"]> {
	const builder = makeBuilder(opts, () => threadIdRef.value);
	// MemorySaver is process-local, fine for the demo. Production
	// would swap in `@langchain/langgraph-checkpoint-sqlite` so the
	// state survives restarts of the callback receiver.
	return builder.compile({ checkpointer: new MemorySaver() });
}

function makeBuilder(opts: BuildGraphOptions, threadId: () => string) {
	return new StateGraph(RefundState)
		.addNode("checkPolicy", makeCheckPolicy(opts))
		.addNode("humanReview", makeHumanReview(opts, threadId))
		.addNode("autoApprove", autoApproveNode)
		.addEdge(START, "checkPolicy")
		.addConditionalEdges("checkPolicy", (state) =>
			state.autoApproved ? "autoApprove" : "humanReview",
		)
		.addEdge("autoApprove", END)
		.addEdge("humanReview", END);
}
