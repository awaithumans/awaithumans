/**
 * Cross-runtime env-var lookup.
 *
 * `process.env` only exists on Node. Bun + Deno expose equivalent APIs
 * through their own namespaces; edge runtimes and browsers have none.
 * `globalThis.process` is typed as `undefined` by the DOM lib, so we
 * narrow via a typed shim rather than sprinkling `any` casts across
 * the SDK.
 *
 * Only called from SDK entry points (awaitHuman). Pure function — no
 * caching. Returns `undefined` when the var isn't set or the runtime
 * has no env surface.
 */

interface EnvHost {
	process?: { env?: Record<string, string | undefined> };
}

export function envVar(name: string): string | undefined {
	const host = globalThis as unknown as EnvHost;
	return host.process?.env?.[name];
}
