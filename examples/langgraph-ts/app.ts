/**
 * Application — graph + checkpointer + HTTP surface, all in one process.
 *
 * Mirrors what a real LangGraph deployment looks like: ONE web server
 * owns the graph, the checkpointer, and the awaithumans webhook
 * receiver. A node calling `awaitHuman` ↔ a webhook that comes back
 * later ↔ a `Command({resume})` invocation are all the same process,
 * the same compiled graph, the same checkpointer.
 *
 * Two routes:
 *
 *   POST /start         {customerId, amountUsd}      → kicks off a graph
 *                                                       run; returns the
 *                                                       thread id and the
 *                                                       interrupt info
 *                                                       (or final result
 *                                                       if auto-approved)
 *
 *   POST /awaithumans/cb?thread=<thread_id>           → awaithumans webhook;
 *                                                       resumes the graph
 *
 * Run with:
 *   AWAITHUMANS_PAYLOAD_KEY=$(cat <discovery>/payload.key) npm run app
 *
 * Then in another terminal:
 *   npm run kickoff -- 250 cus_demo
 */

import { randomUUID } from "node:crypto";

import { serve } from "@hono/node-server";
import { Command, type CompiledStateGraph } from "@langchain/langgraph";
import { resolveAdminToken, resolveServerUrl } from "awaithumans";
import { createLangGraphCallbackHandler } from "awaithumans/langgraph";
import { Hono } from "hono";

import {
	type RefundStateType,
	buildRefundGraph,
} from "./graph.js";

const PORT = Number(process.env.PORT ?? "8765");
const CALLBACK_BASE = process.env.AWAITHUMANS_CALLBACK_BASE ?? `http://localhost:${PORT}`;

async function main(): Promise<void> {
	const payloadKey = process.env.AWAITHUMANS_PAYLOAD_KEY;
	if (!payloadKey) {
		console.error(
			"AWAITHUMANS_PAYLOAD_KEY is required.\n" +
				"  Dev: export AWAITHUMANS_PAYLOAD_KEY=$(cat .awaithumans/payload.key) " +
				"(from wherever you ran `awaithumans dev`).",
		);
		process.exit(1);
	}

	// awaithumans config — same chain `awaitHuman` uses internally.
	// Explicit option → AWAITHUMANS_URL / TOKEN env vars → discovery
	// file written by `awaithumans dev` → defaults.
	const serverUrl = await resolveServerUrl();
	const apiKey = await resolveAdminToken();
	if (!apiKey) {
		console.error(
			"Couldn't find an admin token. Run `awaithumans dev` " +
				"(writes ~/.awaithumans-dev.json) or export " +
				"AWAITHUMANS_ADMIN_API_TOKEN.",
		);
		process.exit(1);
	}

	// The threadId-via-ref trick: `humanReviewNode` reads the current
	// thread id off this object. We update it before each .invoke()
	// call so the node knows which thread its callback URL should
	// encode. A more idiomatic approach would thread `RunnableConfig`
	// through node signatures — keeping this simple for the example.
	const threadIdRef = { value: "<unset>" };
	const graph = buildRefundGraph(
		{
			awaithumans: { serverUrl, apiKey, callbackBase: CALLBACK_BASE },
			autoApproveThresholdUsd: 100,
		},
		threadIdRef,
	) as unknown as CompiledStateGraph<
		RefundStateType,
		Partial<RefundStateType>
	>;

	const handleCallback = createLangGraphCallbackHandler({
		graph,
		command: Command,
		payloadKey,
	});

	const app = new Hono();

	// ── /start ────────────────────────────────────────────────────────
	// Kicks off a refund run. Returns either the final state (if
	// auto-approved) or the interrupt payload (if a human is needed).
	app.post("/start", async (c) => {
		const body = await c.req.json<{ customerId?: string; amountUsd?: number }>();
		if (typeof body.amountUsd !== "number" || !body.customerId) {
			return c.json({ error: "customerId and amountUsd required" }, 400);
		}

		const threadId = `refund-${randomUUID()}`;
		threadIdRef.value = threadId;

		const result = (await graph.invoke(
			{ customerId: body.customerId, amountUsd: body.amountUsd },
			{ configurable: { thread_id: threadId } },
		)) as RefundStateType;

		// `.invoke()` in LangGraph TS returns the state values that
		// were committed up to the pause point — it does NOT surface
		// a `__interrupt__` field (that's a `.stream()`-only shape).
		// Pending interrupts live on `getState().tasks[].interrupts`,
		// so the right "are we paused?" check is to look for any
		// task that has an unresumed interrupt.
		const state = await graph.getState({
			configurable: { thread_id: threadId },
		});
		const interrupts = state.tasks.flatMap((t) => t.interrupts ?? []);
		if (interrupts.length > 0) {
			console.log(`[start] graph paused thread=${threadId}`);
			return c.json({ threadId, status: "interrupted", interrupts });
		}

		console.log(
			`[start] graph finished thread=${threadId} approved=${result.approved}`,
		);
		return c.json({ threadId, status: "completed", state: result });
	});

	// ── /awaithumans/cb ───────────────────────────────────────────────
	// awaithumans server POSTs here when the human submits. The handler
	// verifies HMAC, then calls graph.invoke(Command({resume: <body>}))
	// against the right thread.
	app.post("/awaithumans/cb", async (c) => {
		const thread = c.req.query("thread");
		if (!thread) {
			return c.text("missing thread", 400);
		}
		const body = await c.req.arrayBuffer();
		const sig = c.req.header("x-awaithumans-signature");

		// Setting the ref BEFORE the resume isn't strictly needed —
		// after this resume the humanReview node won't run again on
		// this thread. But if the graph had MULTIPLE interrupts on
		// the same thread, the next interrupt would need this set.
		threadIdRef.value = thread;

		const out = await handleCallback({
			threadId: thread,
			body,
			signatureHeader: sig,
		});

		if (out.error) {
			console.warn(`[cb] thread=${thread} ${out.status}: ${out.error}`);
			return c.text(out.error, out.status as 200 | 400 | 401 | 500);
		}
		console.log(`[cb] thread=${thread} resumed`);

		// Read the final state off the checkpointer and surface it so
		// the kickoff client can poll for it (in a real system this
		// would be exposed via a more idiomatic /threads/{id} route).
		const finalState = await graph.getState({
			configurable: { thread_id: thread },
		});
		return c.json({ ok: true, state: finalState.values });
	});

	// ── /threads/:id ──────────────────────────────────────────────────
	// Lets the kickoff client poll for completion.
	app.get("/threads/:id", async (c) => {
		const id = c.req.param("id");
		const state = await graph.getState({ configurable: { thread_id: id } });
		return c.json({
			threadId: id,
			values: state.values,
			interrupts: state.tasks.flatMap((t) => t.interrupts ?? []),
		});
	});

	console.log(`[app] graph + callback at http://localhost:${PORT}`);
	console.log(`[app] awaithumans server: ${serverUrl}`);
	console.log(`[app] callback base (in webhook URL): ${CALLBACK_BASE}`);
	serve({ fetch: app.fetch, port: PORT });
}

main().catch((err) => {
	console.error("[app] fatal:", err);
	process.exit(1);
});
