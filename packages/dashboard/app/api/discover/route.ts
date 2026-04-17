/**
 * Server-side discovery route.
 *
 * Reads the discovery file written by `awaithumans dev` (at ~/.awaithumans-dev.json)
 * and returns the API server URL. Verifies the server PID is still alive
 * before trusting the file — if the PID is dead, the file is stale and ignored.
 *
 * Precedence:
 *   1. NEXT_PUBLIC_API_URL env var
 *   2. Discovery file (if PID is alive)
 *   3. Default: http://localhost:3001
 */

import { readFile, unlink } from "node:fs/promises";
import { homedir } from "node:os";
import { join } from "node:path";

import { DEFAULT_API_URL } from "@/lib/constants";

export const dynamic = "force-dynamic";

const DISCOVERY_FILE = ".awaithumans-dev.json";

interface DiscoveryFile {
	url: string;
	host: string;
	port: number;
	pid: number;
	started_at: string;
}

function isProcessAlive(pid: number): boolean {
	try {
		// process.kill(pid, 0) sends the null signal — checks if the process
		// exists without actually killing it. Throws if the process is gone.
		process.kill(pid, 0);
		return true;
	} catch (err) {
		// ESRCH = no such process. EPERM = process exists but we can't signal it.
		if ((err as NodeJS.ErrnoException).code === "EPERM") return true;
		return false;
	}
}

async function readDiscoveryFile(): Promise<DiscoveryFile | null> {
	const path = join(homedir(), DISCOVERY_FILE);
	let data: DiscoveryFile;
	try {
		const contents = await readFile(path, "utf-8");
		data = JSON.parse(contents) as DiscoveryFile;
	} catch {
		return null;
	}

	if (typeof data.url !== "string" || typeof data.pid !== "number") {
		return null;
	}

	// Verify the server is still running. If not, clean up the stale file.
	if (!isProcessAlive(data.pid)) {
		try {
			await unlink(path);
		} catch {
			// Ignore — file may already be gone
		}
		return null;
	}

	return data;
}

export async function GET() {
	const envUrl = process.env.NEXT_PUBLIC_API_URL;
	if (envUrl) {
		return Response.json({ url: envUrl, source: "env" });
	}

	const discovered = await readDiscoveryFile();
	if (discovered) {
		return Response.json({ url: discovered.url, source: "discovery" });
	}

	return Response.json({ url: DEFAULT_API_URL, source: "default" });
}
