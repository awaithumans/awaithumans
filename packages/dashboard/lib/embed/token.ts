"use client";

/*
 * Embed token lives in the URL fragment (`#token=...`). Reading
 * `location.hash` is client-only — fragments never reach the server,
 * never appear in access logs, never appear in the Referer header on
 * cross-origin subresource loads. See spec §4.1 for the rationale.
 */

export function extractEmbedToken(): string | null {
	if (typeof window === "undefined") return null;
	const hash = window.location.hash.replace(/^#/, "");
	if (!hash) return null;
	const params = new URLSearchParams(hash);
	return params.get("token");
}
