import type { Metadata } from "next";

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
				{children}
			</body>
		</html>
	);
}
