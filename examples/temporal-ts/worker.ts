/**
 * Temporal worker — runs the refund workflow.
 *
 * Three things to know:
 *
 *   1. The worker bundles the workflow files via Temporal's
 *      sandbox-friendly bundler (`workflowsPath`). Files referenced
 *      from the workflow can't reach `process.env`, `fs`, network,
 *      etc. — anything that needs those goes in `activities/`.
 *
 *   2. Activities run in a normal Node context. They DO see env
 *      vars, can hit databases, call third parties, etc. The
 *      `processRefund` stand-in lives in `activities/process-refund.ts`.
 *
 *   3. The temporal adapter's `awaitHuman` is also workflow-safe
 *      (it uses `proxyActivities` internally to POST the task).
 *      Workflow code calls it directly; the adapter handles the
 *      sandbox crossing.
 *
 * Run with:
 *   npm install
 *   npm run worker
 *
 * In separate terminals:
 *   - `temporal server start-dev`              — Temporal cluster
 *   - `awaithumans dev`                        — awaithumans server
 *   - `npm run callback-server`                — callback receiver
 *   - `npm run kickoff -- 250`                 — start a workflow run
 */

import { fileURLToPath } from "node:url";

import { NativeConnection, Worker } from "@temporalio/worker";

import { processRefund } from "./activities/process-refund.js";

const TASK_QUEUE = "awaithumans-refunds";
const TEMPORAL_ADDRESS = process.env.TEMPORAL_ADDRESS ?? "localhost:7233";

async function main(): Promise<void> {
	const connection = await NativeConnection.connect({
		address: TEMPORAL_ADDRESS,
	});

	const worker = await Worker.create({
		connection,
		taskQueue: TASK_QUEUE,
		// Temporal's TS bundler reads workflow files at startup. We
		// pass the directory absolute so it works regardless of the
		// caller's cwd.
		workflowsPath: fileURLToPath(new URL("./workflows", import.meta.url)),
		activities: { processRefund },
	});

	console.log(`[worker] task_queue=${TASK_QUEUE}`);
	console.log(`[worker] Temporal at ${TEMPORAL_ADDRESS}`);
	console.log("[worker] running — Ctrl-C to stop");

	await worker.run();
}

main().catch((err) => {
	console.error("[worker] fatal:", err);
	process.exit(1);
});
