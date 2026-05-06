/**
 * End-to-end real-delivery email test (TypeScript).
 *
 * Same shape as `examples/email-smoke/` but configured for an actual
 * email provider — you receive the email in your real inbox and
 * click the magic-link button by hand. The SDK long-polls until the
 * action endpoint records your decision.
 *
 * Pick a transport via env:
 *
 *   AWAITHUMANS_TEST_TRANSPORT=resend RESEND_API_KEY=re_... \
 *     RECIPIENT_EMAIL=you@example.com \
 *     [FROM_EMAIL=onboarding@resend.dev] \
 *     npm start
 *
 *   AWAITHUMANS_TEST_TRANSPORT=smtp \
 *     SMTP_HOST=smtp.gmail.com SMTP_PORT=587 \
 *     SMTP_USER=you@gmail.com SMTP_PASSWORD=<app password> \
 *     RECIPIENT_EMAIL=you@example.com \
 *     FROM_EMAIL=you@gmail.com \
 *     npm start
 *
 * The script reuses an identity named `email-e2e-real` across runs
 * so you don't have to re-verify a sender. Re-running with new
 * transport_config upserts in place — no duplicate-id error.
 *
 * Prerequisites:
 *   - `awaithumans dev` running in another terminal (the SDK reads
 *     URL + admin token from the discovery file, no env-var dance)
 *   - For Resend: a Resend account + API key. The `onboarding@resend.dev`
 *     sender works without domain verification.
 *   - For SMTP: a working SMTP host (Gmail / SES / Mailgun / your
 *     preferred provider). Gmail requires an App Password
 *     (https://myaccount.google.com/apppasswords).
 */

import {
	awaitHuman,
	resolveAdminToken,
	resolveServerUrl,
} from "awaithumans";
import { z } from "zod";

// ─── Resolve config ────────────────────────────────────────────────────

const SERVER_URL = (await resolveServerUrl()).replace(/\/$/, "");
const ADMIN_TOKEN = await resolveAdminToken();

if (!ADMIN_TOKEN) {
	console.error(
		"Couldn't find an admin token. Run `awaithumans dev` first " +
			"(writes ~/.awaithumans-dev.json), or export " +
			"AWAITHUMANS_ADMIN_API_TOKEN.",
	);
	process.exit(1);
}

const RECIPIENT = process.env.RECIPIENT_EMAIL;
if (!RECIPIENT) {
	console.error("RECIPIENT_EMAIL is required — your real inbox.");
	process.exit(1);
}

const TRANSPORT = process.env.AWAITHUMANS_TEST_TRANSPORT ?? "resend";
const IDENTITY_ID = "email-e2e-real";

// ─── Build transport_config from env ───────────────────────────────────

interface TransportSetup {
	from_email: string;
	transport: string;
	transport_config: Record<string, unknown>;
}

function buildTransportSetup(): TransportSetup {
	if (TRANSPORT === "resend") {
		const apiKey = process.env.RESEND_API_KEY;
		if (!apiKey) {
			console.error("RESEND_API_KEY required when transport=resend.");
			process.exit(1);
		}
		return {
			from_email: process.env.FROM_EMAIL ?? "onboarding@resend.dev",
			transport: "resend",
			transport_config: { api_key: apiKey },
		};
	}

	if (TRANSPORT === "smtp") {
		const host = process.env.SMTP_HOST;
		const fromEmail = process.env.FROM_EMAIL;
		if (!host || !fromEmail) {
			console.error(
				"SMTP_HOST and FROM_EMAIL required when transport=smtp.",
			);
			process.exit(1);
		}
		return {
			from_email: fromEmail,
			transport: "smtp",
			transport_config: {
				host,
				port: Number(process.env.SMTP_PORT ?? 587),
				username: process.env.SMTP_USER,
				password: process.env.SMTP_PASSWORD,
				start_tls: true,
			},
		};
	}

	console.error(
		`Unknown transport '${TRANSPORT}'. Valid: resend, smtp. ` +
			"(The `file` and `logging` transports are dev-only — see " +
			"examples/email-smoke for that.)",
	);
	process.exit(1);
}

// ─── Identity setup (idempotent upsert) ────────────────────────────────

async function configureIdentity(setup: TransportSetup): Promise<void> {
	const resp = await fetch(
		`${SERVER_URL}/api/channels/email/identities`,
		{
			method: "POST",
			headers: {
				Authorization: `Bearer ${ADMIN_TOKEN}`,
				"Content-Type": "application/json",
			},
			body: JSON.stringify({
				id: IDENTITY_ID,
				display_name: "awaithumans e2e real",
				from_email: setup.from_email,
				from_name: "awaithumans test",
				reply_to: null,
				transport: setup.transport,
				transport_config: setup.transport_config,
			}),
		},
	);
	if (!resp.ok) {
		console.error(
			`identity setup failed (${resp.status}): ${await resp.text()}`,
		);
		process.exit(1);
	}
	console.log(
		`→ identity '${IDENTITY_ID}' configured (transport=${setup.transport}, from=${setup.from_email})`,
	);
}

// ─── Run ───────────────────────────────────────────────────────────────

async function main(): Promise<void> {
	console.log(`→ server: ${SERVER_URL}`);
	console.log(`→ recipient: ${RECIPIENT}`);
	console.log(`→ transport: ${TRANSPORT}`);

	await configureIdentity(buildTransportSetup());

	console.log("");
	console.log(
		"→ creating task — check your inbox in a few seconds and click " +
			"the Approve button to complete it",
	);

	// Single-boolean response → email renderer emits Approve / Reject
	// magic-link buttons inline. Multi-field responses fall back to a
	// "Review in dashboard" link-out, also valid but less snappy for
	// a manual demo.
	const decision = await awaitHuman({
		task: "Approve this real-delivery test",
		payloadSchema: z.object({
			note: z.string(),
			sentAt: z.string(),
		}),
		payload: {
			note: "If you received this email, awaithumans → real-mail integration works.",
			sentAt: new Date().toISOString(),
		},
		responseSchema: z.object({
			approved: z.boolean().describe("Approve this test?"),
		}),
		// 30-minute window — generous so you have time to find the
		// email, click through, and walk back. The Slack/email
		// post-completion updater will mark the message done either
		// way.
		timeoutMs: 30 * 60_000,
		notify: [`email+${IDENTITY_ID}:${RECIPIENT}`],
		idempotencyKey: `email-e2e-real:${Date.now()}`,
	});

	console.log("");
	if (decision.approved) {
		console.log("✓ Approved — task completed end-to-end via real email");
	} else {
		console.log("✗ Rejected — task completed end-to-end via real email");
	}
}

main().catch((err) => {
	console.error("✗ failed:", err);
	process.exit(1);
});
