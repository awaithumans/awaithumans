#!/usr/bin/env node
// npx awaithumans <args> — thin wrapper that runs the Python CLI via uv.
//
// Why uv: a single pre-built binary that resolves + fetches + runs a
// Python package in one step. No pip, no venv, no "which python".
// TS developers never touch a Python environment.
//
// Why not bundle a Python interpreter: tripling the npm install size
// for something `uv` does natively on every major platform.

import { spawn, spawnSync } from "node:child_process";
import { platform } from "node:process";

const DOCS_URL = "https://awaithumans.dev/docs/install";
const UV_INSTALL_URL = "https://docs.astral.sh/uv/getting-started/installation/";
const PIP_SPEC = "awaithumans[server]";

function hasUv() {
	const probe = spawnSync("uv", ["--version"], { stdio: "ignore" });
	return probe.status === 0;
}

function printMissingUv() {
	const installCmd =
		platform === "win32"
			? 'powershell -c "irm https://astral.sh/uv/install.ps1 | iex"'
			: "curl -LsSf https://astral.sh/uv/install.sh | sh";

	process.stderr.write(
		[
			"",
			"  awaithumans: `uv` is required but was not found on PATH.",
			"",
			"  The TS wrapper runs the Python server via `uv` so you don't",
			"  have to manage a Python environment yourself.",
			"",
			"  Install uv:",
			`    ${installCmd}`,
			"",
			`  Or see ${UV_INSTALL_URL}`,
			`  More: ${DOCS_URL}`,
			"",
			"",
		].join("\n"),
	);
}

function main() {
	if (!hasUv()) {
		printMissingUv();
		process.exit(1);
	}

	const child = spawn(
		"uvx",
		["--from", PIP_SPEC, "awaithumans", ...process.argv.slice(2)],
		{ stdio: "inherit" },
	);

	child.on("exit", (code, signal) => {
		if (signal) {
			process.kill(process.pid, signal);
			return;
		}
		process.exit(code ?? 0);
	});

	for (const sig of ["SIGINT", "SIGTERM"]) {
		process.on(sig, () => child.kill(sig));
	}
}

main();
