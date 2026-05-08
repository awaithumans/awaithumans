"use client";

/*
 * Bearer-auth fetch helper for the embed page. The token from the URL
 * fragment is sent in the Authorization header — never in cookies,
 * never in another query string. See spec §5.1 (bearer-only auth).
 *
 * The dashboard talks to the API at the same origin in production
 * (the static dashboard is bundled into the Python package and served
 * at the same host as the API). In dev, NEXT_PUBLIC_API_URL can point
 * at a separate dev server.
 */

const DEFAULT_API_URL = "http://localhost:3001";

export interface EmbedFetchOptions extends Omit<RequestInit, "headers"> {
	token: string;
}

export class EmbedFetchError extends Error {
	constructor(
		public readonly code: string,
		message: string,
	) {
		super(message);
		this.name = "EmbedFetchError";
	}
}

function getApiBase(): string {
	if (typeof window !== "undefined") {
		const overridden = (
			window as unknown as { __AWAITHUMANS_API_URL__?: string }
		).__AWAITHUMANS_API_URL__;
		if (overridden) return overridden;
	}
	const fromEnv = process.env.NEXT_PUBLIC_API_URL;
	return fromEnv ?? DEFAULT_API_URL;
}

export async function embedFetch<T>(
	path: string,
	{ token, ...init }: EmbedFetchOptions,
): Promise<T> {
	const base = getApiBase().replace(/\/$/, "");
	const res = await fetch(`${base}${path}`, {
		...init,
		headers: {
			"Content-Type": "application/json",
			Authorization: `Bearer ${token}`,
		},
	});
	if (!res.ok) {
		let body: { error?: { code?: string; message?: string } } = {};
		try {
			body = (await res.json()) as typeof body;
		} catch {
			// non-JSON error body — keep defaults
		}
		throw new EmbedFetchError(
			body.error?.code ?? `HTTP_${res.status}`,
			body.error?.message ?? res.statusText,
		);
	}
	return (await res.json()) as T;
}
