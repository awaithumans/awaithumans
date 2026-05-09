/**
 * Mint embed tokens from a partner backend. Counterpart to Python's
 * `awaithumans.embed.embed_token`. See spec §4.4.
 */

import type { EmbedTokenOptions, EmbedTokenResult } from "./types/embed.js";

const DEFAULT_SERVER = "http://localhost:3001";

export async function embedToken(
	opts: EmbedTokenOptions,
): Promise<EmbedTokenResult> {
	const g = globalThis as unknown as {
		window?: unknown;
		process?: { env?: Record<string, string | undefined> };
	};
	if (typeof g.window !== "undefined") {
		// eslint-disable-next-line no-console
		console.warn(
			"[awaithumans] service keys (ah_sk_...) must be server-side only.",
		);
	}

	const envServer =
		g.process !== undefined ? g.process.env?.AWAITHUMANS_URL : undefined;
	const base = (opts.serverUrl ?? envServer ?? DEFAULT_SERVER).replace(
		/\/$/,
		"",
	);

	const body: Record<string, unknown> = {
		task_id: opts.taskId,
		parent_origin: opts.parentOrigin,
	};
	if (opts.sub !== undefined) body.sub = opts.sub;
	if (opts.ttlSeconds !== undefined) body.ttl_seconds = opts.ttlSeconds;

	const res = await fetch(`${base}/api/embed/tokens`, {
		method: "POST",
		headers: {
			"Content-Type": "application/json",
			Authorization: `Bearer ${opts.apiKey}`,
		},
		body: JSON.stringify(body),
	});
	if (!res.ok) {
		let parsed: { error?: { code?: string; message?: string } } = {};
		try {
			parsed = (await res.json()) as typeof parsed;
		} catch {
			// non-JSON error body
		}
		throw new Error(
			parsed.error?.message ??
				`Embed mint failed: HTTP ${res.status} ${res.statusText}`,
		);
	}
	const data = (await res.json()) as {
		embed_token: string;
		embed_url: string;
		expires_at: string;
	};
	return {
		embedToken: data.embed_token,
		embedUrl: data.embed_url,
		expiresAt: data.expires_at,
	};
}
