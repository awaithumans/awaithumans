"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
	Activity,
	BarChart3,
	ListChecks,
	Settings as SettingsIcon,
} from "lucide-react";

import { APP_VERSION, DOCS_BASE_URL, GITHUB_URL } from "@/lib/constants";
import { cn } from "@/lib/utils";
import { Wordmark } from "./logo";

type NavItem = {
	href: string;
	icon: typeof Activity;
	label: string;
	/** If set, match these prefixes as "active" (e.g. /tasks/[id] → highlight /). */
	activeWhenPrefix?: string[];
};

const NAV: NavItem[] = [
	{ href: "/", icon: ListChecks, label: "Tasks", activeWhenPrefix: ["/tasks"] },
	{ href: "/audit", icon: Activity, label: "Audit log" },
	{ href: "/analytics", icon: BarChart3, label: "Analytics" },
	{ href: "/settings", icon: SettingsIcon, label: "Settings" },
];

export function Sidebar() {
	const pathname = usePathname();

	return (
		<aside className="w-60 shrink-0 border-r border-white/[0.07] flex flex-col bg-bg">
			{/* Logo */}
			<div className="px-5 py-[22px] border-b border-white/[0.07]">
				<Link
					href="/"
					aria-label="Home"
					className="block focus:outline-none focus:ring-2 focus:ring-brand/40 rounded-sm"
				>
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
								"relative flex items-center gap-3 pl-3 pr-3 py-2 rounded-md text-sm transition-colors",
								active
									? "text-fg bg-white/[0.04]"
									: "text-white/55 hover:text-white hover:bg-white/[0.02]",
							)}
						>
							{active && (
								<span
									className="absolute left-0 top-1.5 bottom-1.5 w-0.5 rounded-r-full bg-brand"
									aria-hidden
								/>
							)}
							<Icon
								size={16}
								className={cn(
									"transition-colors",
									active ? "text-brand" : "text-white/40",
								)}
							/>
							<span>{item.label}</span>
						</Link>
					);
				})}
			</nav>

			{/* Footer */}
			<div className="px-5 py-4 border-t border-white/[0.07] text-xs">
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
				<div className="text-white/25 font-mono text-[11px]">{APP_VERSION}</div>
			</div>
		</aside>
	);
}
