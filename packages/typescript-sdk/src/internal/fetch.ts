/**
 * `fetch` + `AbortController` + `ServerUnreachableError` in one call.
 *
 * Both `createTask` and `pollUntilTerminal` repeat the same pattern:
 * spin up a controller, set a timer, wrap the fetch in try/catch/
 * finally, map transport failures to our typed error. This helper
 * owns that shape so the call sites read as HTTP intent only.
 *
 * Leaves status-code handling to the caller — different routes map
 * non-2xx to different SDK errors (TaskCreateError, PollError, etc.).
 */

import { ServerUnreachableError } from "../errors.js";

export async function fetchWithTimeout(
	url: string,
	init: RequestInit,
	timeoutMs: number,
	/** Origin shown in the ServerUnreachableError message when the network fails. */
	serverOrigin: string,
): Promise<Response> {
	const controller = new AbortController();
	const timer = setTimeout(() => controller.abort(), timeoutMs);
	try {
		return await fetch(url, { ...init, signal: controller.signal });
	} catch (err) {
		throw new ServerUnreachableError(serverOrigin, err);
	} finally {
		clearTimeout(timer);
	}
}
