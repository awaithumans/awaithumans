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

import { createRequire } from "node:module";
import { dirname } from "node:path";
import { fileURLToPath } from "node:url";

import { NativeConnection, Worker } from "@temporalio/worker";
import { awaithumansCreateTask } from "awaithumans/temporal";

import { processRefund } from "./activities/process-refund.js";

const require = createRequire(import.meta.url);
const TEMPORAL_WORKFLOW_DIR = dirname(
	require.resolve("@temporalio/workflow/package.json"),
);

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
		// `awaithumansCreateTask` is the activity the temporal adapter's
		// `awaitHuman` schedules — it POSTs to the awaithumans server.
		// Has to be registered worker-side; the workflow proxy that
		// calls it lives in `awaithumans/temporal`.
		activities: { processRefund, awaithumansCreateTask },
		// When `awaithumans` is installed via `file:` (or `npm link`),
		// the package's own `node_modules` can shadow this app's copy
		// of `@temporalio/workflow`. Two copies = two `CancellationScope`
		// classes = "Cannot read private member #cancelRequested" at
		// runtime. Aliasing pins every import to one resolved path.
		bundlerOptions: {
			webpackConfigHook: (config) => {
				config.resolve = config.resolve ?? {};
				config.resolve.alias = {
					...(config.resolve.alias as Record<string, string> | undefined),
					"@temporalio/workflow$": TEMPORAL_WORKFLOW_DIR,
				};
				return config;
			},
		},
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
