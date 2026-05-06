/**
 * TS counterpart of `examples/slack-native/refund.py` — delegate a
 * task to a Slack user via DM, await their decision in TypeScript.
 *
 * What happens:
 *
 *   1. The TS SDK creates a task with `notify=["slack:@TA"]`.
 *   2. The server resolves `@TA` against the directory (the implicit-
 *      assignee derivation pins TA as `assigned_to_user_id`), then
 *      DMs them via the Slack channel.
 *   3. TA sees the DM with two buttons:
 *        - "Approve in Slack" — opens the Block-Kit modal in place
 *        - "Open in Dashboard" — signed handoff URL (works even if
 *          TA has no email/password)
 *   4. TA submits via either path. The Slack message updates to
 *      "Completed by @TA" with no buttons (so they can't re-trigger).
 *   5. This script's `awaitHuman` resolves with the typed response.
 *
 * Prerequisites:
 *
 *   - `awaithumans dev` running (the SDK reads its discovery file
 *     for URL + admin token; no env-var dance needed)
 *   - Slack app linked + workspace OAuth completed (one-time setup;
 *     see examples/slack-native/README.md)
 *   - User `TA` added to the directory with a Slack handle, via the
 *     dashboard's Users → Add user form
 *
 * Run:
 *
 *     cd examples/slack-native-ts
 *     npm install
 *     npm start
 */

import { awaitHuman } from "awaithumans";
import { z } from "zod";

// ─── Schemas ───────────────────────────────────────────────────────────

// What TA sees while reviewing.
const WireTransfer = z.object({
	transferId: z.string(),
	amountUsd: z.number(),
	to: z.string(),
});

// IMPORTANT: a single boolean response triggers the email/Slack
// renderer's compact magic-link / button path. Multi-field responses
// fall back to "open the form" — still works, but the demo's less
// snappy. Keep this single-field so the Slack DM has Approve/Reject
// buttons inline.
const Approval = z.object({
	approved: z
		.boolean()
		.describe("Approve this wire transfer?"),
});

// ─── Config ────────────────────────────────────────────────────────────

// The Slack handle we're tagging. Change this to whatever you set
// when you added the user in the dashboard.
const SLACK_HANDLE = "TA";

// ─── Run ───────────────────────────────────────────────────────────────

async function main(): Promise<void> {
	const transferId = `WT-${Date.now().toString(36).toUpperCase()}`;
	console.log(`→ creating task — notify=slack:@${SLACK_HANDLE}`);
	console.log(`  transfer_id=${transferId}`);

	const decision = await awaitHuman({
		task: "Approve this wire transfer",
		payloadSchema: WireTransfer,
		payload: {
			transferId,
			amountUsd: 12_500,
			to: "Acme Inc.",
		},
		responseSchema: Approval,
		// 15-minute window — generous for a manual demo. The Slack
		// message stays interactive that whole time; after expiry it
		// auto-updates to "Timed out" via the post-completion updater.
		timeoutMs: 15 * 60_000,
		// Single notify entry → implicit-assignee derivation fires
		// server-side, marking TA as `assigned_to_user_id`. Without
		// this binding, the Slack `view_submission` auth check would
		// reject TA's submission as "not assigned to you."
		notify: [`slack:@${SLACK_HANDLE}`],
		// Stable idempotency so a re-run during the same wall-clock
		// second returns the existing task instead of stacking
		// duplicates. In production, tie this to a real business
		// identifier (transferId here is fine because we generated
		// it just above).
		idempotencyKey: `slack-ts-demo:${transferId}`,
	});

	console.log("");
	if (decision.approved) {
		console.log(`✓ Approved by @${SLACK_HANDLE}`);
	} else {
		console.log(`✗ Rejected by @${SLACK_HANDLE}`);
	}
	console.log(`  full response: ${JSON.stringify(decision)}`);
}

main().catch((err) => {
	console.error("✗ failed:", err);
	process.exit(1);
});
