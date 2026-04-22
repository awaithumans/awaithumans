"use client";

import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { fetchMe, fetchSetupStatus } from "@/lib/server";
import { TerminalSpinner } from "./terminal-spinner";

type State = "loading" | "allowed" | "redirecting";

/**
 * Dashboard auth gate. On mount:
 *
 * - If setup hasn't been completed → redirect to /setup
 * - If /api/auth/me says `authenticated: true` → allow
 * - Otherwise → redirect to /login?next=<current path>
 *
 * Keeps it to at most two calls per mount; subsequent API calls either
 * ride the session cookie or get 401 → UnauthorizedError, which the
 * callers surface as a banner.
 */
export function AuthGuard({ children }: { children: React.ReactNode }) {
	const router = useRouter();
	const pathname = usePathname();
	const [state, setState] = useState<State>("loading");

	useEffect(() => {
		let cancelled = false;

		(async () => {
			try {
				const setup = await fetchSetupStatus();
				if (cancelled) return;
				if (setup.needs_setup) {
					setState("redirecting");
					router.replace("/setup");
					return;
				}

				const me = await fetchMe();
				if (cancelled) return;
				if (me.authenticated) {
					setState("allowed");
				} else {
					setState("redirecting");
					router.replace(`/login?next=${encodeURIComponent(pathname)}`);
				}
			} catch {
				if (cancelled) return;
				// /me or /setup/status fails (server down): let the
				// underlying page render its own error — don't trap the
				// user in a loading state.
				setState("allowed");
			}
		})();

		return () => {
			cancelled = true;
		};
	}, [router, pathname]);

	if (state === "loading" || state === "redirecting") {
		return (
			<div className="min-h-screen flex items-center justify-center">
				<TerminalSpinner
					label={state === "redirecting" ? "redirecting" : "awaiting session"}
				/>
			</div>
		);
	}

	return <>{children}</>;
}
