/**
 * Public discovery helpers — `resolveAdminToken` / `resolveServerUrl`.
 *
 * Mirrors the Python `resolve_admin_token` / `resolve_server_url`
 * tests. The internal `resolveDiscoveryConfig` is already covered by
 * its own behaviour in `await-human.test.ts`; this file pins the
 * public surface (precedence between explicit option / env var /
 * discovery file).
 */

import { afterEach, beforeEach, describe, expect, it } from "vitest";

import { resolveAdminToken, resolveServerUrl } from "../src/discovery";
import { _setDiscoveryCacheForTesting } from "../src/internal/discovery";

const ENV_TOKEN_KEY = "AWAITHUMANS_ADMIN_API_TOKEN";
const ENV_URL_KEY = "AWAITHUMANS_URL";

let savedToken: string | undefined;
let savedUrl: string | undefined;

beforeEach(() => {
	savedToken = process.env[ENV_TOKEN_KEY];
	savedUrl = process.env[ENV_URL_KEY];
	delete process.env[ENV_TOKEN_KEY];
	delete process.env[ENV_URL_KEY];
	// Pin the discovery cache so tests don't depend on the developer's
	// local `~/.awaithumans-dev.json`.
	_setDiscoveryCacheForTesting({});
});

afterEach(() => {
	if (savedToken === undefined) delete process.env[ENV_TOKEN_KEY];
	else process.env[ENV_TOKEN_KEY] = savedToken;
	if (savedUrl === undefined) delete process.env[ENV_URL_KEY];
	else process.env[ENV_URL_KEY] = savedUrl;
});

// ─── resolveAdminToken ─────────────────────────────────────────────────

describe("resolveAdminToken", () => {
	it("returns explicit token when supplied", async () => {
		process.env[ENV_TOKEN_KEY] = "env-loses";
		_setDiscoveryCacheForTesting({ adminToken: "discovery-loses" });

		const out = await resolveAdminToken({ explicitToken: "explicit-wins" });

		expect(out).toBe("explicit-wins");
	});

	it("falls back to env var when no explicit token", async () => {
		process.env[ENV_TOKEN_KEY] = "env-token";
		_setDiscoveryCacheForTesting({ adminToken: "discovery-loses" });

		const out = await resolveAdminToken();

		expect(out).toBe("env-token");
	});

	it("falls back to discovery file when env unset", async () => {
		_setDiscoveryCacheForTesting({ adminToken: "discovery-token" });

		const out = await resolveAdminToken();

		expect(out).toBe("discovery-token");
	});

	it("returns undefined when nothing is configured", async () => {
		const out = await resolveAdminToken();
		expect(out).toBeUndefined();
	});
});

// ─── resolveServerUrl ──────────────────────────────────────────────────

describe("resolveServerUrl", () => {
	it("returns explicit URL when supplied", async () => {
		process.env[ENV_URL_KEY] = "http://env-loses.local";
		_setDiscoveryCacheForTesting({ url: "http://discovery-loses.local" });

		const out = await resolveServerUrl({
			explicitUrl: "http://explicit-wins.local",
		});

		expect(out).toBe("http://explicit-wins.local");
	});

	it("falls back to env var when no explicit URL", async () => {
		process.env[ENV_URL_KEY] = "http://env.local";
		_setDiscoveryCacheForTesting({ url: "http://discovery-loses.local" });

		const out = await resolveServerUrl();

		expect(out).toBe("http://env.local");
	});

	it("falls back to discovery file when env unset", async () => {
		_setDiscoveryCacheForTesting({ url: "http://discovery.local:3091" });

		const out = await resolveServerUrl();

		expect(out).toBe("http://discovery.local:3091");
	});

	it("returns the localhost default when nothing is configured", async () => {
		const out = await resolveServerUrl();
		// Default lives in `internal/constants.ts`. Pin it so a
		// regression there doesn't silently change the SDK's
		// default endpoint.
		expect(out).toBe("http://localhost:3001");
	});
});
