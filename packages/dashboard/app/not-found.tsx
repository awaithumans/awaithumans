import Link from "next/link";

import { LogoMark } from "@/components/logo";

/**
 * 404 page — shell-prompt flavour.
 *
 * Rendered for any route that doesn't match. We keep it monospace + tight
 * so it feels like part of the product, not a generic "oops" dead-end.
 */
export default function NotFound() {
	return (
		<div className="min-h-screen flex items-center justify-center px-6">
			<div className="w-full max-w-md font-mono">
				<div className="flex items-center gap-2.5 mb-8">
					<LogoMark size={20} className="text-fg" />
					<span className="font-semibold tracking-tight">awaithumans</span>
				</div>

				<div className="border border-white/10 rounded-lg bg-white/[0.015] overflow-hidden">
					<div className="px-5 py-4 text-sm border-b border-white/5">
						<span className="text-white/30 mr-2">$</span>
						<span className="text-fg">awaithumans find</span>
						<span className="text-white/40"> &lt;this-page&gt;</span>
					</div>

					<div className="px-5 py-4 space-y-1 text-xs">
						<Line prefix="!" className="text-red-400/90">
							no such route
						</Line>
						<Line prefix="#" className="text-white/40">
							the URL you hit isn't part of the dashboard
						</Line>
					</div>

					<div className="px-5 py-4 border-t border-white/5 space-y-2 text-xs">
						<div className="text-white/40 mb-2">did you mean:</div>
						<Suggestion href="/" command="awaithumans tasks" />
						<Suggestion href="/audit" command="awaithumans audit" />
						<Suggestion href="/analytics" command="awaithumans stats" />
						<Suggestion href="/settings" command="awaithumans config" />
					</div>
				</div>

				<p className="mt-6 text-[11px] text-white/25 text-center">
					404 · task not found
				</p>
			</div>
		</div>
	);
}

function Line({
	prefix,
	className,
	children,
}: {
	prefix: string;
	className?: string;
	children: React.ReactNode;
}) {
	return (
		<div className={className}>
			<span className="text-white/25 mr-1.5">{prefix}</span>
			{children}
		</div>
	);
}

function Suggestion({ href, command }: { href: string; command: string }) {
	return (
		<Link
			href={href}
			className="flex items-center gap-2 text-white/60 hover:text-brand transition-colors group"
		>
			<span className="text-white/25 group-hover:text-brand/60 transition-colors">
				→
			</span>
			<span>{command}</span>
		</Link>
	);
}
