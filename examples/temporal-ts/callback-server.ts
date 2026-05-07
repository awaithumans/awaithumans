/**
 * Callback receiver — converts awaithumans webhooks to Temporal signals.
 *
 * Mirror of `examples/temporal/callback_server.py` (Python). The two
 * receivers are interchangeable: a Python workflow can be signaled by
 * the TS receiver and vice versa, because the wire format and signal
 * naming are identical across SDKs.
 *
 * Three things this does:
 *
 *   1. Receives POST /awaithumans/callback?wf=<workflow_id>
 *   2. Verifies the HMAC signature header against PAYLOAD_KEY
 *   3. Looks up the workflow by ID and signals it with the response
 *
 * Uses Hono — small, runtime-portable web framework. Same shape would
 * work with Express, Fastify, Bun.serve, etc.
 *
 * Run with:
 *   npm run callback-server
 *
 * For the awaithumans server (running locally) to reach this from
 * Docker / a hosted deployment, expose it via a tunnel:
 *   ngrok http 8765
 *   export AWAITHUMANS_CALLBACK_BASE=https://<ngrok-id>.ngrok.io
 *
 * AWAITHUMANS_PAYLOAD_KEY must be set on BOTH this process and the
 * awaithumans server — that's how HMAC keys derive to the same value.
 */

import { serve } from "@hono/node-server";
import { Client, Connection } from "@temporalio/client";
import { dispatchSignal } from "awaithumans/temporal";
import { Hono } from "hono";

const TEMPORAL_ADDRESS = process.env.TEMPORAL_ADDRESS ?? "localhost:7233";
const PORT = Number(process.env.PORT ?? "8765");

async function main(): Promise<void> {
	const payloadKey = process.env.AWAITHUMANS_PAYLOAD_KEY;
	if (!payloadKey) {
		// In dev, `awaithumans dev` writes the key to a discovery file
		// AND exports it as an env var inside its own process. The
		// callback receiver runs separately and needs the same key —
		// either export it manually, or read the dev key file.
		console.error(
			"AWAITHUMANS_PAYLOAD_KEY is required.\n" +
				"  Dev: export AWAITHUMANS_PAYLOAD_KEY=$(cat .awaithumans/payload.key) " +
				"(from wherever you ran `awaithumans dev`).",
		);
		process.exit(1);
	}

	// Long-lived Temporal client — opening one per request would
	// burn ~50ms on handshake.
	const connection = await Connection.connect({ address: TEMPORAL_ADDRESS });
	const temporalClient = new Client({ connection });
	console.log(`[callback] connected to Temporal at ${TEMPORAL_ADDRESS}`);

	// Wrap the Temporal client in the structural interface
	// `dispatchSignal` expects — keeps the SDK adapter free of a
	// hard `@temporalio/client` import.
	const clientLike = {
		getHandle(workflowId: string) {
			return temporalClient.workflow.getHandle(workflowId);
		},
	};

	const app = new Hono();

	app.post("/awaithumans/callback", async (c) => {
		const workflowId = c.req.query("wf");
		if (!workflowId) {
			return c.json({ error: "missing wf query param" }, 400);
		}

		const body = await c.req.arrayBuffer();
		const signature = c.req.header("x-awaithumans-signature") ?? null;

		try {
			await dispatchSignal({
				temporalClient: clientLike,
				workflowId,
				body,
				signatureHeader: signature,
				payloadKey,
			});
		} catch (err) {
			const msg = (err as Error).message;
			// Bad signature is a security event; malformed body is a
			// misconfig. Both bubble to the awaithumans server's
			// webhook-failed log.
			if (msg.includes("Invalid awaithumans webhook signature")) {
				console.warn("[callback] rejected bad signature");
				return c.json({ error: msg }, 401);
			}
			console.warn("[callback] rejected:", msg);
			return c.json({ error: msg }, 400);
		}

		return c.json({ ok: true });
	});

	serve({ fetch: app.fetch, port: PORT }, (info) => {
		console.log(`[callback] listening on http://localhost:${info.port}`);
	});
}

main().catch((err) => {
	console.error("[callback] fatal:", err);
	process.exit(1);
});
