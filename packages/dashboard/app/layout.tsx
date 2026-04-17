import type { Metadata } from "next";
import Link from "next/link";
import "./globals.css";

export const metadata: Metadata = {
	title: "awaithumans — Dashboard",
	description: "The human layer for AI agents. Review and complete tasks.",
};

export default function RootLayout({
	children,
}: {
	children: React.ReactNode;
}) {
	return (
		<html lang="en" className="dark">
			<body className="min-h-screen bg-bg text-fg font-mono antialiased">
				<nav className="border-b border-white/10 px-6 py-4 flex items-center justify-between">
					<div className="flex items-center gap-3">
						<span className="text-brand font-bold text-lg">awaithumans</span>
						<span className="text-white/40 text-sm">dashboard</span>
					</div>
					<div className="flex items-center gap-6 text-sm">
						<Link href="/" className="text-white/60 hover:text-white transition-colors">
							Tasks
						</Link>
						<Link href="/audit" className="text-white/60 hover:text-white transition-colors">
							Audit Log
						</Link>
					</div>
				</nav>
				<main className="px-6 py-6">{children}</main>
			</body>
		</html>
	);
}
