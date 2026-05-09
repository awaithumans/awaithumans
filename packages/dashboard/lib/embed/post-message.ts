"use client";

/*
 * One-way iframe → parent postMessage protocol. Every event carries
 * `source: "awaithumans"` so partner-side listeners can filter cleanly
 * (a single window may host multiple iframes, all postMessage-ing into
 * the same `message` listener). See spec §4.5.
 *
 * The parent origin is the EXPLICIT `targetOrigin` argument — we read
 * it from the JWT's `parent_origin` claim, not from `*`. The browser
 * silently drops the message if the actual parent's origin doesn't
 * match, which is the security guarantee.
 */

export type EmbedEvent =
	| { type: "loaded"; payload: { taskId: string } }
	| {
			type: "task.completed";
			payload: { taskId: string; response: unknown; completedAt: string };
	  }
	| {
			type: "task.error";
			payload: { taskId: string; code: string; message: string };
	  }
	| { type: "resize"; payload: { height: number } };

const SOURCE = "awaithumans" as const;

export function postEmbed(parentOrigin: string, event: EmbedEvent): void {
	if (typeof window === "undefined" || !window.parent) return;
	if (!parentOrigin) return;
	window.parent.postMessage({ source: SOURCE, ...event }, parentOrigin);
}
