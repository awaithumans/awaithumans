/**
 * Public dev-server discovery helpers.
 *
 * Mirror of `awaithumans.utils.discovery` on the Python side. Lets
 * tooling (smoke tests, examples, custom scripts) resolve the
 * dev-server URL + admin token using the same precedence the SDK
 * uses internally:
 *
 *     explicit option → env var → discovery file → default / undefined
 *
 * The discovery file at `~/.awaithumans-dev.json` is written by
 * `awaithumans dev`; reading it is the trick that makes both SDKs
 * "just work" without an env-var dance.
 */

import { DEFAULT_SERVER_URL } from "./internal/constants.js";
import { resolveDiscoveryConfig } from "./internal/discovery.js";
import { envVar } from "./internal/env.js";

export type { DiscoveryConfig } from "./internal/discovery.js";
export { resolveDiscoveryConfig } from "./internal/discovery.js";

/**
 * Resolve the admin bearer token the SDK should send.
 *
 * Same precedence as Python's `resolve_admin_token`:
 *
 *   1. explicit `explicitToken` argument
 *   2. `AWAITHUMANS_ADMIN_API_TOKEN` env var
 *   3. discovery file at `~/.awaithumans-dev.json` (dev-only)
 *   4. undefined — request goes out without a bearer header
 *
 * Returns undefined when none of the layers produce a value; callers
 * decide whether to error or proceed anonymously.
 */
export async function resolveAdminToken(
	options?: { explicitToken?: string },
): Promise<string | undefined> {
	if (options?.explicitToken) return options.explicitToken;
	const env = envVar("AWAITHUMANS_ADMIN_API_TOKEN");
	if (env) return env;
	const config = await resolveDiscoveryConfig();
	return config.adminToken;
}

/**
 * Resolve the awaithumans server URL the SDK should hit.
 *
 * Same precedence as Python's `resolve_server_url`:
 *
 *   1. explicit `explicitUrl` argument
 *   2. `AWAITHUMANS_URL` env var
 *   3. discovery file (dev-server bound URL)
 *   4. `http://localhost:3001` default
 */
export async function resolveServerUrl(
	options?: { explicitUrl?: string },
): Promise<string> {
	if (options?.explicitUrl) return options.explicitUrl;
	const env = envVar("AWAITHUMANS_URL");
	if (env) return env;
	const config = await resolveDiscoveryConfig();
	return config.url ?? DEFAULT_SERVER_URL;
}
