/**
 * Read the dev-server discovery file written by `awaithumans dev`.
 *
 * Mirrors `awaithumans/utils/discovery.py`. The dev CLI drops a JSON
 * file at `~/.awaithumans-dev.json` containing the bound URL plus the
 * auto-generated admin token; the SDK reads it so users don't have to
 * `export AWAITHUMANS_ADMIN_API_TOKEN=$(cat ...)` before every run.
 *
 * Resolution order (matches `client.py`'s `resolve_admin_token` /
 * `resolve_server_url`):
 *
 *     explicit option → env var → discovery file → default / undefined
 *
 * Cross-runtime safety: the SDK has to work in Bun, Deno, edge
 * runtimes, and browsers. Of those only Node + Bun + Deno expose
 * `node:fs`/`os`, and only via dynamic import. We swallow every
 * failure and return an empty config — the SDK falls back to defaults
 * and the server's auth response tells the user what's missing.
 */

interface DiscoveryFile {
	url?: string;
	host?: string;
	port?: number;
	pid?: number;
	started_at?: string;
	admin_token?: string;
}

export interface DiscoveryConfig {
	/** Server URL the dev CLI bound to, e.g. `http://localhost:3001`. */
	url?: string;
	/** Auto-generated admin bearer token. */
	adminToken?: string;
}

const DISCOVERY_FILE_NAME = ".awaithumans-dev.json";

let _cached: DiscoveryConfig | null = null;

/**
 * Best-effort: read the dev-server config dropped by `awaithumans dev`.
 * Returns `{}` when the file doesn't exist / can't be read / we're
 * in a non-Node runtime.
 *
 * Memoized for the process lifetime — agents call awaitHuman in a
 * hot loop and we don't want a stat per task. Restarting the dev
 * server invalidates the cached config; restart the agent too in
 * that case.
 */
export async function resolveDiscoveryConfig(): Promise<DiscoveryConfig> {
	if (_cached !== null) return _cached;
	_cached = await readDiscovery();
	return _cached;
}

// ─── Internals ─────────────────────────────────────────────────────────

interface FsModule {
	readFile(p: string, enc: string): Promise<string>;
}
interface OsModule {
	homedir(): string;
}
interface PathModule {
	join(...parts: string[]): string;
}

// Indirected import specs so TypeScript can't statically resolve them
// against `@types/node` — keeps the SDK's type surface free of Node-
// specific globals (the SDK has to compile cleanly for Bun/Deno/edge
// targets too). Resolution happens at runtime; failures fall through
// to `{}`.
const NODE_FS_PROMISES = "node:fs/promises";
const NODE_OS = "node:os";
const NODE_PATH = "node:path";

async function readDiscovery(): Promise<DiscoveryConfig> {
	// Dynamic imports so module load doesn't blow up in browser /
	// edge-runtime contexts that lack node:* — we just return {}.
	let fsMod: FsModule | undefined;
	let osMod: OsModule | undefined;
	let pathMod: PathModule | undefined;
	try {
		fsMod = (await import(NODE_FS_PROMISES)) as unknown as FsModule;
		osMod = (await import(NODE_OS)) as unknown as OsModule;
		pathMod = (await import(NODE_PATH)) as unknown as PathModule;
	} catch {
		return {};
	}
	if (!fsMod || !osMod || !pathMod) return {};

	const filePath = pathMod.join(osMod.homedir(), DISCOVERY_FILE_NAME);

	let raw: string;
	try {
		raw = await fsMod.readFile(filePath, "utf8");
	} catch {
		// Missing file is the common case — first-run before
		// `awaithumans dev` has been launched, or running in an
		// environment without a HOME directory.
		return {};
	}

	let parsed: DiscoveryFile;
	try {
		parsed = JSON.parse(raw) as DiscoveryFile;
	} catch {
		// Hand-edited or partially-written file — pretend it's not
		// there rather than crash the SDK on startup.
		return {};
	}

	// Stale-PID detection. The Python SDK does this via os.kill(pid, 0).
	// On Node we use process.kill(pid, 0) — same idiom, also non-
	// destructive (signal 0 is "permission probe, no actual signal").
	// When the dev server crashed without cleanup the file is left
	// behind; trusting its config would mean sending a stale bearer
	// to whatever else is bound on that port.
	if (typeof parsed.pid === "number" && !isProcessAlive(parsed.pid)) {
		return {};
	}

	const config: DiscoveryConfig = {};
	if (typeof parsed.url === "string" && parsed.url) {
		config.url = parsed.url;
	}
	if (typeof parsed.admin_token === "string" && parsed.admin_token) {
		config.adminToken = parsed.admin_token;
	}
	return config;
}

interface KillableProcess {
	kill?(pid: number, signal: 0): void;
}

function isProcessAlive(pid: number): boolean {
	const proc = (globalThis as { process?: KillableProcess }).process;
	if (!proc?.kill) return true; // can't tell — best-effort: trust it
	try {
		proc.kill(pid, 0);
		return true;
	} catch (err) {
		const code = (err as { code?: string }).code;
		if (code === "ESRCH") return false; // No such process
		// EPERM: process exists, we just can't signal — treat as alive.
		return true;
	}
}

/** Test-only: drop the cache so a follow-up read picks up a new file. */
export function _resetDiscoveryCache(): void {
	_cached = null;
}

/**
 * Test-only: pin the discovery result to a fixed config without
 * touching the filesystem. Lets unit tests assert against the
 * "no discovery file" or "specific discovery file" cases without
 * depending on what the developer has running locally.
 */
export function _setDiscoveryCacheForTesting(config: DiscoveryConfig): void {
	_cached = config;
}
