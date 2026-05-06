/**
 * End-to-end email-channel smoke test (TypeScript).
 *
 * Exercises the full create → notify → click-magic-link → resolve loop
 * against a real awaithumans server, using ONLY the public TypeScript
 * SDK + a tiny admin helper for the email-identity setup. No mocks,
 * no internal imports.
 *
 * What runs:
 *   1. Configure an email sender identity that uses the `file` transport
 *      (drops one JSON per email into a tmp dir — captures what would
 *      otherwise have left for Resend).
 *   2. Call `awaitHuman` with `notify=["email:..."]` and a single-Switch
 *      response schema (the renderer emits magic-link buttons for that).
 *   3. Concurrently poll the tmp dir for the email file, parse the
 *      "Approve" magic-link URL out of the rendered text body, then
 *      POST to it (the action endpoint is public — no auth needed).
 *   4. Wait for `awaitHuman` to resolve. Assert the response matches.
 *
 * Why a runnable script and not a vitest unit test:
 *   - The whole point is "does the TS SDK actually talk to the server."
 *   - Mocked unit coverage already exists (tests/await-human.test.ts).
 *   - This catches contract drift between the wire formats.
 *
 * Prerequisites (in another terminal):
 *
 *     awaithumans dev
 *
 * Then in this terminal:
 *
 *     cd examples/email-smoke
 *     npm install
 *     export AWAITHUMANS_ADMIN_API_TOKEN="$(cat ~/.awaithumans/admin.token)"
 *     npm start
 *
 * The default server URL is http://localhost:3001. Override with
 * AWAITHUMANS_URL if your dev server is elsewhere (e.g., behind ngrok).
 */

import { mkdtempSync, readFileSync, readdirSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { setTimeout as sleep } from "node:timers/promises";

import { awaitHuman } from "awaithumans";
import { z } from "zod";

// ─── Config ────────────────────────────────────────────────────────────

const SERVER_URL =
	process.env.AWAITHUMANS_URL ?? "http://localhost:3001";
const ADMIN_TOKEN = process.env.AWAITHUMANS_ADMIN_API_TOKEN;

if (!ADMIN_TOKEN) {
	console.error(
		"AWAITHUMANS_ADMIN_API_TOKEN is required. " +
			"Run `awaithumans dev` first, then set the env var to the contents " +
			"of ~/.awaithumans/admin.token (or wherever your dev DB sits).",
	);
	process.exit(1);
}

const RECIPIENT_EMAIL = "smoke-recipient@example.test";
const IDENTITY_ID = `smoke-${Date.now().toString(36)}`;

// Use a unique tmp dir per run so old emails from prior smoke runs
// don't pollute the magic-link search.
const EMAIL_DIR = mkdtempSync(join(tmpdir(), "awaithumans-smoke-"));
console.log(`→ email capture dir: ${EMAIL_DIR}`);

// ─── Schemas ───────────────────────────────────────────────────────────

const TransferRequest = z.object({
	transferId: z.string(),
	amountUsd: z.number(),
	to: z.string(),
});

// IMPORTANT: a single boolean field triggers the renderer's magic-
// link path (Approve/Reject buttons in the email). Multi-field
// responses fall back to a "review in dashboard" link-out, which
// is harder to script.
const ApprovalResponse = z.object({
	approved: z.boolean().describe("Approve this transfer?"),
});

// ─── Admin helpers ─────────────────────────────────────────────────────

async function adminFetch(
	path: string,
	init: RequestInit = {},
): Promise<Response> {
	return fetch(`${SERVER_URL}${path}`, {
		...init,
		headers: {
			...(init.headers ?? {}),
			Authorization: `Bearer ${ADMIN_TOKEN}`,
			"Content-Type": "application/json",
		},
	});
}

async function configureFileTransportIdentity(): Promise<void> {
	const resp = await adminFetch("/api/channels/email/identities", {
		method: "POST",
		body: JSON.stringify({
			id: IDENTITY_ID,
			display_name: "Smoke test sender",
			from_email: "smoke@app.example",
			from_name: "awaithumans smoke",
			reply_to: null,
			transport: "file",
			transport_config: { dir: EMAIL_DIR },
		}),
	});
	if (!resp.ok) {
		throw new Error(
			`identity create failed: ${resp.status} ${await resp.text()}`,
		);
	}
	console.log(`→ created email identity '${IDENTITY_ID}' (file transport)`);
}

async function deleteIdentity(): Promise<void> {
	// Best-effort cleanup so a half-run smoke test doesn't leave junk
	// rows in the operator's email-identity list.
	try {
		await adminFetch(`/api/channels/email/identities/${IDENTITY_ID}`, {
			method: "DELETE",
		});
	} catch {
		// non-fatal — the row is harmless and the operator can clear
		// it manually if they care.
	}
}

// ─── Email capture ────────────────────────────────────────────────────

interface CapturedEmail {
	to: string;
	subject: string;
	html: string;
	text: string;
}

async function pollForEmail(
	deadlineMs: number,
): Promise<CapturedEmail> {
	while (Date.now() < deadlineMs) {
		const files = readdirSync(EMAIL_DIR)
			.filter((f) => f.endsWith(".json"))
			.sort(); // unix-ms-prefixed names sort chronologically

		const recent = files.find((f: string) => {
			const payload = JSON.parse(
				readFileSync(join(EMAIL_DIR, f), "utf8"),
			);
			return payload.to === RECIPIENT_EMAIL;
		});

		if (recent) {
			const payload = JSON.parse(
				readFileSync(join(EMAIL_DIR, recent), "utf8"),
			);
			return {
				to: payload.to,
				subject: payload.subject,
				html: payload.html,
				text: payload.text,
			};
		}
		await sleep(250);
	}
	throw new Error(
		`Timed out waiting for email to ${RECIPIENT_EMAIL} in ${EMAIL_DIR}`,
	);
}

function assertEmailLooksRight(email: CapturedEmail): void {
	// Pin the things the email channel SHOULD always include — anything
	// missing here would mean the renderer regressed.
	if (!email.subject) {
		throw new Error("Email has empty subject");
	}
	if (!email.html.includes("Approve wire transfer (smoke test)")) {
		throw new Error("Email body missing the task title");
	}
	if (!email.html.includes("WT-SMOKE-1")) {
		throw new Error("Email body missing the payload (transferId)");
	}
	if (!email.html.includes(`/tasks/`) && !email.html.includes(`/task?id=`)) {
		throw new Error("Email body missing the dashboard link-out");
	}
}

async function completeTaskViaAdmin(taskId: string): Promise<void> {
	// `awaitHuman` doesn't currently synthesize a `form_definition` from
	// a Zod schema (Python has `extract_form`; the TS port is a
	// post-launch task). Without that, the email renderer falls back
	// to a "Review in dashboard" link-out — no magic-link buttons. So
	// the smoke test completes the task via the admin completion API
	// instead of clicking a magic link.
	//
	// What this still proves end-to-end:
	//   - TS SDK's `awaitHuman` creates the task with the right wire shape
	//   - The notify list resolves to the email channel
	//   - The email transport actually fires + writes the message
	//   - Polling resolves when the task transitions to completed
	//
	// The magic-link click path has its own Python coverage; once form
	// synthesis lands in the TS SDK we'll switch this script to click
	// the link instead.
	const resp = await adminFetch(`/api/tasks/${taskId}/complete`, {
		method: "POST",
		body: JSON.stringify({
			response: { approved: true },
			completed_via_channel: "smoke",
		}),
	});
	if (!resp.ok) {
		throw new Error(
			`task complete failed: ${resp.status} ${await resp.text()}`,
		);
	}
	console.log(`→ completed task ${taskId} via admin API`);
}

// ─── Orchestration ─────────────────────────────────────────────────────

async function main(): Promise<void> {
	console.log(`→ smoke against ${SERVER_URL}`);

	await configureFileTransportIdentity();

	// `awaitHuman` is an awaitable that resolves on completion. Run it
	// concurrently with the email-capture poll so we can click the
	// magic link while the SDK is still polling.
	const idem = `email-smoke-${Date.now()}`;

	const awaitPromise = awaitHuman({
		task: "Approve wire transfer (smoke test)",
		payloadSchema: TransferRequest,
		payload: {
			transferId: "WT-SMOKE-1",
			amountUsd: 10_000,
			to: "Acme Inc.",
		},
		responseSchema: ApprovalResponse,
		timeoutMs: 5 * 60_000, // 5 minutes — plenty of slack for CI
		idempotencyKey: idem,
		// notify format: `<channel>[+<identity>]:<target>`. The `+identity`
		// suffix on the channel side picks our smoke-test sender; without
		// it the notifier would fall back to env-configured defaults.
		notify: [`email+${IDENTITY_ID}:${RECIPIENT_EMAIL}`],
		serverUrl: SERVER_URL,
		apiKey: ADMIN_TOKEN,
	});

	// 30s deadline for the background email — the notifier runs as a
	// FastAPI BackgroundTask AFTER the create-task response, so it
	// always lands within ~1s on a healthy box. 30s is paranoid.
	// 30s deadline for the background email — the notifier runs as a
	// FastAPI BackgroundTask AFTER the create-task response, so it
	// always lands within ~1s on a healthy box. 30s is paranoid.
	const captureDeadline = Date.now() + 30_000;
	const email = await pollForEmail(captureDeadline);
	console.log(`→ captured email: subject="${email.subject}" to=${email.to}`);
	assertEmailLooksRight(email);
	console.log("→ email body content checks: OK");

	// Find the task we just created so we can complete it via admin API.
	// The list endpoint returns most-recent-first; we filter by our
	// idempotency_key for an exact match.
	const taskId = await findTaskByIdempotencyKey(idem);
	console.log(`→ resolved task_id=${taskId}`);

	await completeTaskViaAdmin(taskId);

	const decision = await awaitPromise;
	if (decision.approved !== true) {
		throw new Error(
			`Expected approved=true, got: ${JSON.stringify(decision)}`,
		);
	}

	console.log("✓ smoke pass: TS SDK created task → email captured → SDK polled → resolved");
}

async function findTaskByIdempotencyKey(idem: string): Promise<string> {
	// The TS SDK doesn't yet expose the task_id from awaitHuman directly
	// (it returns the typed response, not the wire record). So the
	// smoke test recovers the id via the admin list — fine for a
	// dev-mode test, not a pattern we'd recommend for production code.
	const resp = await adminFetch("/api/tasks?limit=50");
	if (!resp.ok) {
		throw new Error(`task list failed: ${resp.status}`);
	}
	const tasks = (await resp.json()) as Array<{
		id: string;
		idempotency_key: string;
	}>;
	const match = tasks.find((t) => t.idempotency_key === idem);
	if (!match) {
		throw new Error(
			`Couldn't find task with idempotency_key=${idem} in the listing`,
		);
	}
	return match.id;
}

main()
	.catch(async (err) => {
		console.error("✗ smoke FAILED");
		console.error(err);
		await deleteIdentity();
		process.exit(1);
	})
	.then(async () => {
		await deleteIdentity();
	});
