"use client";

import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";

import { LogoMark } from "@/components/logo";
import { TerminalSpinner } from "@/components/terminal-spinner";
import { login, fetchMe } from "@/lib/server";

/**
 * Wrapping the search-params reader in Suspense is required for
 * Next's static export (output: "export"). Without it, the build
 * fails with "useSearchParams() should be wrapped in a suspense
 * boundary at page /login". Split so the `?next=` lookup is inside
 * the boundary and the page shell renders statically.
 */
export default function LoginPage() {
	return (
		<Suspense
			fallback={
				<div className="min-h-screen flex items-center justify-center">
					<TerminalSpinner label="checking session" />
				</div>
			}
		>
			<LoginPageInner />
		</Suspense>
	);
}

function LoginPageInner() {
	const router = useRouter();
	const params = useSearchParams();
	const next = params.get("next") || "/";

	const [user, setUser] = useState("admin");
	const [password, setPassword] = useState("");
	const [submitting, setSubmitting] = useState(false);
	const [error, setError] = useState<string | null>(null);
	const [authRequired, setAuthRequired] = useState<boolean | null>(null);

	// If the server has auth off, bounce straight through.
	useEffect(() => {
		fetchMe()
			.then((me) => {
				if (!me.auth_enabled) {
					router.replace(next);
				} else {
					setAuthRequired(true);
					if (me.authenticated) router.replace(next);
				}
			})
			.catch(() => setAuthRequired(true));
	}, [router, next]);

	const handleSubmit = async (e: React.FormEvent) => {
		e.preventDefault();
		setSubmitting(true);
		setError(null);
		try {
			await login(user, password);
			router.replace(next);
		} catch (err) {
			setError(
				err instanceof Error && err.message.includes("401")
					? "Invalid credentials."
					: "Sign-in failed. Check the server is reachable.",
			);
		} finally {
			setSubmitting(false);
		}
	};

	// Don't flash the login form while we're checking session state.
	if (authRequired === null) {
		return (
			<div className="min-h-screen flex items-center justify-center">
				<TerminalSpinner label="checking session" />
			</div>
		);
	}

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
					<h1 className="text-lg font-semibold mb-1">Sign in</h1>
					<p className="text-white/40 text-xs mb-5">
						Enter the dashboard password configured for this server.
					</p>

					<form onSubmit={handleSubmit} className="space-y-4">
						<Field
							label="Username"
							value={user}
							onChange={setUser}
							autoFocus={!user}
							disabled={submitting}
						/>
						<Field
							label="Password"
							type="password"
							value={password}
							onChange={setPassword}
							autoFocus={!!user}
							disabled={submitting}
						/>

						{error && (
							<div className="text-red-400 text-xs border border-red-400/30 bg-red-400/5 rounded-md px-3 py-2">
								{error}
							</div>
						)}

						<button
							type="submit"
							disabled={submitting || !password}
							className="w-full px-4 py-2.5 bg-brand text-black font-semibold text-sm rounded-md hover:bg-brand/90 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
						>
							{submitting ? "Signing in…" : "Sign in"}
						</button>
					</form>
				</div>

				<p className="text-center text-white/25 text-xs mt-6">
					Running behind your own auth proxy? Leave{" "}
					<code className="text-white/40">AWAITHUMANS_DASHBOARD_PASSWORD</code>{" "}
					unset to disable this screen.
				</p>
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
