"use client";

import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";

import { LogoMark } from "@/components/logo";
import { TerminalSpinner } from "@/components/terminal-spinner";
import { createFirstOperator, fetchSetupStatus } from "@/lib/server";

/**
 * First-run setup wizard. Creates the initial operator account
 * using the one-shot bootstrap token printed in the server log.
 *
 * If setup is already complete, redirects to /login. Token can be
 * pre-filled from `?token=...` (the server logs a clickable URL
 * with that query param).
 */
export default function SetupPage() {
	return (
		<Suspense
			fallback={
				<div className="min-h-screen flex items-center justify-center">
					<TerminalSpinner label="checking server" />
				</div>
			}
		>
			<SetupPageInner />
		</Suspense>
	);
}

function SetupPageInner() {
	const router = useRouter();
	const params = useSearchParams();

	const [token, setToken] = useState(() => params.get("token") ?? "");
	const [email, setEmail] = useState("");
	const [displayName, setDisplayName] = useState("");
	const [password, setPassword] = useState("");
	const [confirm, setConfirm] = useState("");

	const [submitting, setSubmitting] = useState(false);
	const [error, setError] = useState<string | null>(null);
	const [state, setState] = useState<
		"checking" | "ready" | "already-done" | "unreachable"
	>("checking");

	useEffect(() => {
		(async () => {
			try {
				const status = await fetchSetupStatus();
				if (!status.needs_setup) {
					setState("already-done");
				} else {
					setState("ready");
				}
			} catch {
				setState("unreachable");
			}
		})();
	}, []);

	const handleSubmit = async (e: React.FormEvent) => {
		e.preventDefault();
		setError(null);
		if (password !== confirm) {
			setError("Passwords don't match.");
			return;
		}
		if (password.length < 8) {
			setError("Password must be at least 8 characters.");
			return;
		}

		setSubmitting(true);
		try {
			await createFirstOperator({
				token,
				email,
				password,
				display_name: displayName || undefined,
			});
			// Server sets the session cookie on 201 — land straight on the queue.
			router.replace("/");
		} catch (err) {
			const msg = err instanceof Error ? err.message : String(err);
			if (msg.includes("403")) {
				setError(
					"Setup token rejected. Check the server log for the latest token.",
				);
			} else if (msg.includes("409")) {
				setError("Setup is already complete. Please sign in instead.");
				setState("already-done");
			} else {
				setError(`Setup failed: ${msg}`);
			}
		} finally {
			setSubmitting(false);
		}
	};

	if (state === "checking") {
		return (
			<div className="min-h-screen flex items-center justify-center">
				<TerminalSpinner label="checking server" />
			</div>
		);
	}

	if (state === "already-done") {
		return (
			<Shell title="Setup already complete">
				<p className="text-white/60 text-sm mb-4">
					This server already has an operator account. Sign in with those
					credentials.
				</p>
				<a
					href="/login"
					className="block w-full px-4 py-2.5 bg-brand text-black font-semibold text-sm rounded-md text-center hover:bg-brand/90"
				>
					Go to sign in
				</a>
			</Shell>
		);
	}

	if (state === "unreachable") {
		return (
			<Shell title="Server unreachable">
				<p className="text-white/60 text-sm">
					Can't reach <code>/api/setup/status</code>. Make sure{" "}
					<code>awaithumans dev</code> is running and refresh.
				</p>
			</Shell>
		);
	}

	return (
		<Shell title="First-run setup">
			<p className="text-white/40 text-xs mb-5">
				Create the initial operator account. The setup token was printed to
				the server log when the process started — paste it below.
			</p>

			<form onSubmit={handleSubmit} className="space-y-4">
				<Field
					label="Setup token"
					value={token}
					onChange={setToken}
					disabled={submitting}
					autoFocus={!token}
					type="text"
				/>
				<Field
					label="Email"
					type="email"
					value={email}
					onChange={setEmail}
					disabled={submitting}
					autoFocus={!!token && !email}
				/>
				<Field
					label="Display name (optional)"
					value={displayName}
					onChange={setDisplayName}
					disabled={submitting}
				/>
				<Field
					label="Password"
					type="password"
					value={password}
					onChange={setPassword}
					disabled={submitting}
				/>
				<Field
					label="Confirm password"
					type="password"
					value={confirm}
					onChange={setConfirm}
					disabled={submitting}
				/>

				{error && (
					<div className="text-red-400 text-xs border border-red-400/30 bg-red-400/5 rounded-md px-3 py-2">
						{error}
					</div>
				)}

				<button
					type="submit"
					disabled={submitting || !token || !email || !password || !confirm}
					className="w-full px-4 py-2.5 bg-brand text-black font-semibold text-sm rounded-md hover:bg-brand/90 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
				>
					{submitting ? "Creating…" : "Create operator"}
				</button>
			</form>
		</Shell>
	);
}

function Shell({ title, children }: { title: string; children: React.ReactNode }) {
	return (
		<div className="min-h-screen flex items-center justify-center px-6">
			<div className="w-full max-w-sm">
				<div className="flex items-center gap-2.5 mb-8 justify-center">
					<LogoMark size={24} className="text-fg" />
					<span className="font-mono font-semibold tracking-tight text-base">
						awaithumans
					</span>
				</div>
				<div className="border border-white/10 rounded-lg p-6 bg-white/[0.02]">
					<h1 className="text-lg font-semibold mb-1">{title}</h1>
					{children}
				</div>
			</div>
		</div>
	);
}

function Field({
	label,
	value,
	onChange,
	type = "text",
	autoFocus,
	disabled,
}: {
	label: string;
	value: string;
	onChange: (v: string) => void;
	type?: string;
	autoFocus?: boolean;
	disabled?: boolean;
}) {
	return (
		<label className="block">
			<span className="text-xs font-medium text-white/60 mb-1.5 block">
				{label}
			</span>
			<input
				type={type}
				value={value}
				onChange={(e) => onChange(e.target.value)}
				autoFocus={autoFocus}
				disabled={disabled}
				className="w-full bg-white/5 border border-white/10 rounded-md px-3 py-2 text-sm focus:outline-none focus:border-brand/40 disabled:opacity-40"
			/>
		</label>
	);
}
