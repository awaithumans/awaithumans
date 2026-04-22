/**
 * HTTP client for the awaithumans server.
 *
 * Two modes:
 *
 * - **Bundled** (`NEXT_PUBLIC_AWAITHUMANS_BUNDLED=true` at build time):
 *   the dashboard is served as static files from the Python server
 *   itself, so every API call is same-origin. Base URL is `""` and
 *   fetches use relative paths.
 *
 * - **Dev** (two-server): dashboard on `:3000`, API on `:3001`. We
 *   ask the Next.js-side `/api/discover` route for the current API
 *   origin (picks up whichever port the server actually bound to),
 *   cache for 30s, fall back to DEFAULT_API_URL if unreachable.
 *
 * Per-domain functions (tasks, audit, health) live in sibling files
 * and use apiFetch.
 */

import { DEFAULT_API_URL } from "@/lib/constants";

const BUNDLED_MODE = process.env.NEXT_PUBLIC_AWAITHUMANS_BUNDLED === "true";
const CACHE_TTL_MS = 30_000;
let cachedApiBase: string | null = null;
let cachedAt: number = 0;

function invalidateCache() {
	cachedApiBase = null;
	cachedAt = 0;
}

async function resolveApiBase(forceRefresh = false): Promise<string> {
	// Bundled mode: same origin, always. No discovery, no cache needed.
	if (BUNDLED_MODE) return "";

	if (!forceRefresh && cachedApiBase && Date.now() - cachedAt < CACHE_TTL_MS) {
		return cachedApiBase;
	}

	try {
		const res = await fetch("/api/discover");
		if (res.ok) {
			const data = (await res.json()) as { url: string; source: string };
			cachedApiBase = data.url.replace(/\/$/, "");
			cachedAt = Date.now();
			return cachedApiBase;
		}
	} catch {
		// Discovery route unreachable — fall through to default
	}

	cachedApiBase = DEFAULT_API_URL;
	cachedAt = Date.now();
	return cachedApiBase;
}

export class UnauthorizedError extends Error {
	constructor() {
		super("Unauthorized — please log in.");
		this.name = "UnauthorizedError";
	}
}

export async function apiFetch<T>(path: string, options?: RequestInit): Promise<T> {
	let base = await resolveApiBase();

	const doFetch = (url: string) =>
		fetch(`${url}${path}`, {
			...options,
			// Include the session cookie on every call so the Python
			// server can recognise logged-in requests cross-origin in dev.
			credentials: "include",
			headers: {
				"Content-Type": "application/json",
				...options?.headers,
			},
		});

	let res: Response;
	try {
		res = await doFetch(base);
	} catch {
		// Network error (server gone, port closed) — invalidate cache, rediscover, retry once
		invalidateCache();
		base = await resolveApiBase(true);
		res = await doFetch(base);
	}

	if (res.status === 401) {
		throw new UnauthorizedError();
	}

	if (!res.ok) {
		const body = await res.text();
		throw new Error(`API error ${res.status}: ${body}`);
	}

	// 204 No Content and similar — caller isn't expecting a body.
	if (res.status === 204 || res.headers.get("content-length") === "0") {
		return undefined as T;
	}

	return res.json() as Promise<T>;
}
