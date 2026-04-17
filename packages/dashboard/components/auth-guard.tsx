"use client";

import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { fetchMe } from "@/lib/server";

type State = "loading" | "allowed" | "redirecting";

/**
 * Dashboard auth gate. On mount, calls /api/auth/me:
 *
 * - `auth_enabled: false`   → allow (behind-proxy mode)
 * - `authenticated: true`   → allow
 * - anything else           → redirect to /login?next=<current path>
 *
 * Keeps it to a single call per mount; the subsequent API calls either
 * ride the session cookie or get 401 → UnauthorizedError, which the
 * callers surface as a banner.
 */
export function AuthGuard({ children }: { children: React.ReactNode }) {
	const router = useRouter();
	const pathname = usePathname();
	const [state, setState] = useState<State>("loading");

	useEffect(() => {
		let cancelled = false;

		fetchMe()
			.then((me) => {
				if (cancelled) return;
				if (!me.auth_enabled || me.authenticated) {
					setState("allowed");
				} else {
					setState("redirecting");
					router.replace(`/login?next=${encodeURIComponent(pathname)}`);
				}
			})
			.catch(() => {
				if (cancelled) return;
				// If /me itself fails (server down), let the underlying
				// page render its own error — don't trap the user in a
				// loading state. Callers will surface the fetch error.
				setState("allowed");
			});

		return () => {
			cancelled = true;
		};
	}, [router, pathname]);

	if (state === "loading" || state === "redirecting") {
		return (
			<div className="min-h-screen flex items-center justify-center text-white/30 text-sm">
				Loading…
			</div>
		);
	}

	return <>{children}</>;
}
