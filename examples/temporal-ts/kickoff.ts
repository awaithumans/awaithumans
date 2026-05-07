/**
 * Kickoff — start one refund workflow run.
 *
 * In real production this is the place a web request from your app
 * would land. For the demo, we read the amount from argv and use
 * the dev server's discovery file for URL + token.
 *
 * Usage:
 *   npm run kickoff -- 250
 *   # or:
 *   npm run kickoff       # defaults to $100
 */

import { randomUUID } from "node:crypto";

import { Client, Connection } from "@temporalio/client";
import { resolveAdminToken, resolveServerUrl } from "awaithumans";

import type {
	RefundWorkflowInput,
	RefundWorkflowResult,
} from "./workflows/refund-workflow.js";

const TASK_QUEUE = "awaithumans-refunds";
const TEMPORAL_ADDRESS = process.env.TEMPORAL_ADDRESS ?? "localhost:7233";

async function main(): Promise<void> {
	const amountUsd = Number(process.argv[2] ?? "100");
	const customerId = process.argv[3] ?? "cus_demo";

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

	// Where the awaithumans server posts its completion webhook.
	// Has to be reachable from wherever `awaithumans dev` runs —
	// for local-with-ngrok-tunnel, override with the ngrok URL.
	const callbackBase =
		process.env.AWAITHUMANS_CALLBACK_BASE ?? "http://localhost:8765";

	const connection = await Connection.connect({ address: TEMPORAL_ADDRESS });
	const client = new Client({ connection });

	const workflowId = `refund-${randomUUID()}`;
	const input: RefundWorkflowInput = {
		amountUsd,
		customerId,
		callbackBase,
		serverUrl,
		apiKey,
	};

	const handle = await client.workflow.start("refundWorkflow", {
		args: [input],
		taskQueue: TASK_QUEUE,
		workflowId,
	});

	console.log(`[kickoff] started workflow id=${workflowId}`);
	console.log("[kickoff] waiting for human via dashboard / Slack / email");
	console.log(
		`[kickoff] (review at ${serverUrl.replace(/\/$/, "")}/task?id=...)`,
	);

	const result = (await handle.result()) as RefundWorkflowResult;
	console.log("[kickoff] workflow result:", JSON.stringify(result, null, 2));
}

main().catch((err) => {
	console.error("[kickoff] failed:", err);
	process.exit(1);
});
