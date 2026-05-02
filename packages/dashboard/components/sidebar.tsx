"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import {
	Activity,
	BarChart3,
	ListChecks,
	LogOut,
	Settings as SettingsIcon,
} from "lucide-react";
import { useEffect, useState } from "react";

import { APP_VERSION, DOCS_BASE_URL, GITHUB_URL } from "@/lib/constants";
import { fetchMe, logout, type MeResponse } from "@/lib/server";
import { cn } from "@/lib/utils";
import { Wordmark } from "./logo";

type NavItem = {
	href: string;
	icon: typeof Activity;
	label: string;
	/** If set, match these prefixes as "active" (e.g. /task?id=… → highlight /). */
	activeWhenPrefix?: string[];
};

const NAV: NavItem[] = [
	{ href: "/", icon: ListChecks, label: "Tasks", activeWhenPrefix: ["/task"] },
	{ href: "/audit", icon: Activity, label: "Audit Log" },
	{ href: "/analytics", icon: BarChart3, label: "Analytics" },
	{ href: "/settings", icon: SettingsIcon, label: "Settings" },
];

export function Sidebar() {
	const pathname = usePathname();
	const router = useRouter();
	const [me, setMe] = useState<MeResponse | null>(null);
	const [signingOut, setSigningOut] = useState(false);

	useEffect(() => {
		fetchMe()
			.then(setMe)
			.catch(() => setMe(null));
	}, []);

	const handleSignOut = async () => {
		setSigningOut(true);
		try {
			await logout();
		} finally {
			// Always bounce to login, even if the logout call errored —
			// the session is effectively gone the moment we cleared
			// local state, and leaving the operator stuck on the
			// dashboard after clicking "Sign out" is worse than a
			// best-effort logout that can't reach the server.
			router.replace("/login");
		}
	};

	return (
		// Sticky + h-screen keeps the sidebar pinned to the viewport while
		// the main content scrolls. Without this, tall pages (analytics,
		// settings) leave the nav stranded above the fold.
		<aside className="w-60 shrink-0 border-r border-white/10 flex flex-col bg-bg sticky top-0 h-screen self-start">
			{/* Logo */}
			<div className="px-5 py-5 border-b border-white/10">
				<Link href="/" aria-label="Home">
					<Wordmark />
				</Link>
			</div>

			{/* Nav */}
			<nav className="flex-1 px-3 py-4 space-y-0.5">
				{NAV.map((item) => {
					const active =
						pathname === item.href ||
						(item.activeWhenPrefix?.some((p) => pathname.startsWith(p)) ?? false);
					const Icon = item.icon;
					return (
						<Link
							key={item.href}
							href={item.href}
							className={cn(
								"flex items-center gap-3 px-3 py-2 rounded-md text-sm transition-colors",
								active
									? "bg-white/5 text-fg"
									: "text-white/55 hover:text-white hover:bg-white/[0.03]",
							)}
						>
							<Icon size={16} className={active ? "text-brand" : ""} />
							<span>{item.label}</span>
						</Link>
					);
				})}
			</nav>

			{/* User + sign out */}
			{me?.authenticated && (
				<div className="px-3 py-3 border-t border-white/10">
					<div className="px-2 pb-2">
						<div className="text-[11px] text-white/70 font-medium truncate">
							{me.display_name || me.email || me.user_id}
						</div>
						<div className="text-[10px] text-white/35 truncate">
							{me.is_operator ? "operator" : "user"}
							{me.email && me.display_name ? ` · ${me.email}` : null}
						</div>
					</div>
					<button
						type="button"
						onClick={handleSignOut}
						disabled={signingOut}
						className="w-full flex items-center gap-2 px-3 py-2 rounded-md text-xs text-white/55 hover:text-white hover:bg-white/[0.03] disabled:opacity-40 transition-colors"
					>
						<LogOut size={14} />
						<span>{signingOut ? "Signing out…" : "Sign out"}</span>
					</button>
				</div>
			)}

			{/* Footer */}
			<div className="px-5 py-4 border-t border-white/10 text-xs">
				<div className="flex items-center gap-3 text-white/35 mb-2">
					<a
						href={DOCS_BASE_URL}
						target="_blank"
						rel="noopener noreferrer"
						className="hover:text-white/70 transition-colors"
					>
						Docs
					</a>
					<span className="text-white/15">·</span>
					<a
						href={GITHUB_URL}
						target="_blank"
						rel="noopener noreferrer"
						className="hover:text-white/70 transition-colors"
					>
						GitHub
					</a>
				</div>
				<div className="text-white/25 font-mono">{APP_VERSION}</div>
			</div>
		</aside>
	);
}
