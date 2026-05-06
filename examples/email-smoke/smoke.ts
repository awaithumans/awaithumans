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

import {
	awaitHuman,
	resolveAdminToken,
	resolveServerUrl,
} from "awaithumans";
import { z } from "zod";

// ─── Config ────────────────────────────────────────────────────────────

// Resolve URL + admin token via the same chain `awaitHuman` uses
// internally (explicit → env var → discovery file written by
// `awaithumans dev`). Means the smoke "just works" against a
// running dev server with no env-var dance, mirroring the Python
// SDK's default DX.
const SERVER_URL = (await resolveServerUrl()).replace(/\/$/, "");
const ADMIN_TOKEN = await resolveAdminToken();

if (!ADMIN_TOKEN) {
	console.error(
		"Couldn't find an admin token. Either:\n" +
			"  - Run `awaithumans dev` (writes ~/.awaithumans-dev.json) and try again, OR\n" +
			"  - Export AWAITHUMANS_ADMIN_API_TOKEN with the token your server uses.",
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
}

const ACTION_PATH_RE = /\/api\/channels\/email\/action\/[A-Za-z0-9_\-.]+/;

function findApproveLink(email: CapturedEmail): string {
	// The renderer emits BOTH Approve and Reject buttons for a single
	// Switch field. They appear in declaration order — Approve first
	// (style="primary"), Reject second (style="danger") — per
	// `_buttons_for_form` in the Python renderer. We grab the first
	// match and click it; the smoke test always wants the approve
	// path (so the asserted `approved === true` lines up).
	const match =
		email.text.match(ACTION_PATH_RE) ?? email.html.match(ACTION_PATH_RE);
	if (!match) {
		throw new Error(
			"No magic-link URL found in captured email. Was form_definition " +
				"synthesized? See packages/typescript-sdk/src/forms.ts.\n" +
				`text body:\n${email.text}\n\nhtml body:\n${email.html}`,
		);
	}
	return `${SERVER_URL}${match[0]}`;
}

async function clickMagicLink(url: string): Promise<void> {
	// The action endpoint accepts POST with no body — the value is
	// baked into the signed token. GET renders the "are you sure"
	// confirmation page; POST is what actually completes the task.
	// Public endpoint, no auth needed.
	const resp = await fetch(url, { method: "POST" });
	if (!resp.ok) {
		throw new Error(
			`Magic-link POST returned ${resp.status}: ${await resp.text()}`,
		);
	}
	console.log(`→ POSTed magic-link → ${resp.status}`);
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

	const approveUrl = findApproveLink(email);
	console.log(`→ magic-link URL: ${approveUrl}`);

	await clickMagicLink(approveUrl);

	const decision = await awaitPromise;
	if (decision.approved !== true) {
		throw new Error(
			`Expected approved=true, got: ${JSON.stringify(decision)}`,
		);
	}

	console.log("✓ smoke pass: TS SDK + email channel + magic-link round-trip");
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
