/**
 * HTTP client for the awaithumans server.
 *
 * Handles API base URL discovery (via /api/discover) and the shared
 * apiFetch helper. Per-domain functions (tasks, audit, health) live in
 * sibling files and use apiFetch.
 */

import { DEFAULT_API_URL } from "@/lib/constants";

const CACHE_TTL_MS = 30_000;
let cachedApiBase: string | null = null;
let cachedAt: number = 0;

function invalidateCache() {
	cachedApiBase = null;
	cachedAt = 0;
}

async function resolveApiBase(forceRefresh = false): Promise<string> {
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

export async function apiFetch<T>(path: string, options?: RequestInit): Promise<T> {
	let base = await resolveApiBase();

	const doFetch = (url: string) =>
		fetch(`${url}${path}`, {
			...options,
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

	if (!res.ok) {
		const body = await res.text();
		throw new Error(`API error ${res.status}: ${body}`);
	}

	return res.json() as Promise<T>;
}
