/**
 * Server-side discovery route.
 *
 * Reads the discovery file written by `awaithumans dev` (at ~/.awaithumans-dev.json)
 * and returns the API server URL. Falls back to NEXT_PUBLIC_API_URL or localhost:3001.
 *
 * The browser-side API client hits this route once to learn where the Python
 * API server actually is, regardless of which port it auto-selected.
 */

import { readFile } from "node:fs/promises";
import { homedir } from "node:os";
import { join } from "node:path";

export const dynamic = "force-dynamic";

const DISCOVERY_FILE = ".awaithumans-dev.json";
const DEFAULT_URL = "http://localhost:3001";

interface DiscoveryFile {
	url: string;
	host: string;
	port: number;
	pid: number;
	started_at: string;
}

async function readDiscoveryFile(): Promise<DiscoveryFile | null> {
	try {
		const path = join(homedir(), DISCOVERY_FILE);
		const contents = await readFile(path, "utf-8");
		const data = JSON.parse(contents) as DiscoveryFile;
		if (typeof data.url !== "string") return null;
		return data;
	} catch {
		return null;
	}
}

export async function GET() {
	// Priority: NEXT_PUBLIC_API_URL env var > discovery file > default
	const envUrl = process.env.NEXT_PUBLIC_API_URL;
	if (envUrl) {
		return Response.json({ url: envUrl, source: "env" });
	}

	const discovered = await readDiscoveryFile();
	if (discovered) {
		return Response.json({ url: discovered.url, source: "discovery" });
	}

	return Response.json({ url: DEFAULT_URL, source: "default" });
}
