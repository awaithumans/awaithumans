import type { Metadata } from "next";
import { GeistMono } from "geist/font/mono";
import { GeistSans } from "geist/font/sans";

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
		<html
			lang="en"
			className={`dark ${GeistSans.variable} ${GeistMono.variable}`}
		>
			<body className="min-h-screen bg-bg text-fg font-sans antialiased">
				{children}
			</body>
		</html>
	);
}
