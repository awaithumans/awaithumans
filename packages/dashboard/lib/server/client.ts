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

/**
 * Thrown on any non-ok response that isn't 401. `.message` is the
 * server's human-facing `message` field (e.g. "A user with this email
 * already exists.") — safe to drop into a UI banner directly, with no
 * further processing. `errorCode` and `docsUrl` surface the structured
 * fields for callers who want to link out or switch on the error.
 *
 * The server's centralized exception handler always shapes error
 * responses as `{error, message, docs}` (see
 * `server/core/exceptions.py::service_error_handler`). When a response
 * doesn't match — e.g. a 502 from a misbehaving proxy — we fall back
 * to a generic status-code message so `.message` is still readable.
 */
export class ApiError extends Error {
	readonly status: number;
	readonly errorCode: string | null;
	readonly docsUrl: string | null;

	constructor(
		status: number,
		message: string,
		errorCode: string | null = null,
		docsUrl: string | null = null,
	) {
		super(message);
		this.name = "ApiError";
		this.status = status;
		this.errorCode = errorCode;
		this.docsUrl = docsUrl;
	}
}

interface ServerErrorBody {
	error?: unknown;
	message?: unknown;
	detail?: unknown;
	docs?: unknown;
}

async function buildApiError(res: Response): Promise<ApiError> {
	let body: ServerErrorBody | null = null;
	try {
		body = (await res.json()) as ServerErrorBody;
	} catch {
		// Response wasn't JSON (proxy HTML page, truncated body, etc.).
	}

	const message =
		typeof body?.message === "string" && body.message
			? body.message
			: typeof body?.detail === "string" && body.detail
				? body.detail
				: `Request failed with status ${res.status}.`;

	const errorCode = typeof body?.error === "string" ? body.error : null;
	const docsUrl = typeof body?.docs === "string" ? body.docs : null;
	return new ApiError(res.status, message, errorCode, docsUrl);
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
		throw await buildApiError(res);
	}

	// 204 No Content and similar — caller isn't expecting a body.
	if (res.status === 204 || res.headers.get("content-length") === "0") {
		return undefined as T;
	}

	return res.json() as Promise<T>;
}
