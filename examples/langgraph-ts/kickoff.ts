/**
 * Kickoff — start one refund run by hitting the app's /start endpoint.
 *
 * In a real system this would be a request from the user's product
 * surface (e.g. "customer hits 'request refund'"). For the demo it's
 * a CLI script that:
 *
 *   1. POSTs /start to kick off a graph run
 *   2. If auto-approved: prints the final state and exits
 *   3. If interrupted: polls /threads/{id} until it sees a final
 *      state (the human submits via the dashboard, the awaithumans
 *      webhook fires, the app resumes the graph, and the next poll
 *      sees the result)
 *
 * Usage:
 *   npm run kickoff -- 250 cus_demo
 *   npm run kickoff -- 50 cus_small      # auto-approves under threshold
 */

const APP_URL = process.env.APP_URL ?? "http://localhost:8765";
const POLL_INTERVAL_MS = 2000;
const POLL_MAX_TRIES = 240; // 8 minutes — plenty for a demo

async function main(): Promise<void> {
	const amountUsd = Number(process.argv[2] ?? "250");
	const customerId = process.argv[3] ?? "cus_demo";

	const startResp = await fetch(`${APP_URL}/start`, {
		method: "POST",
		headers: { "Content-Type": "application/json" },
		body: JSON.stringify({ amountUsd, customerId }),
	});
	if (!startResp.ok) {
		console.error(`[kickoff] /start returned ${startResp.status}: ${await startResp.text()}`);
		process.exit(1);
	}
	const start = (await startResp.json()) as {
		threadId: string;
		status: "completed" | "interrupted";
		state?: unknown;
		interrupts?: unknown[];
	};

	if (start.status === "completed") {
		console.log("[kickoff] result:", JSON.stringify(start.state, null, 2));
		return;
	}

	console.log(`[kickoff] thread=${start.threadId} paused — awaiting human`);
	console.log("[kickoff] interrupt payload:");
	console.log(JSON.stringify(start.interrupts, null, 2));

	for (let i = 0; i < POLL_MAX_TRIES; i++) {
		await new Promise((r) => setTimeout(r, POLL_INTERVAL_MS));
		const r = await fetch(`${APP_URL}/threads/${start.threadId}`);
		if (!r.ok) {
			console.error(`[kickoff] poll ${r.status}`);
			continue;
		}
		const s = (await r.json()) as {
			values?: { approved?: boolean; notes?: string };
			interrupts?: unknown[];
		};
		// "Done" = no pending interrupt and `approved` is set.
		if (
			(!s.interrupts || s.interrupts.length === 0) &&
			s.values?.approved !== undefined
		) {
			console.log("[kickoff] result:", JSON.stringify(s.values, null, 2));
			return;
		}
	}
	console.error("[kickoff] timed out waiting for human");
	process.exit(1);
}

main().catch((err) => {
	console.error("[kickoff] failed:", err);
	process.exit(1);
});
