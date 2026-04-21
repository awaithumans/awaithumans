/**
 * awaithumans wordmark — SVG mark + monospace lettering.
 *
 * The mark is a rounded square outline with a brand-green dot pulsing
 * inside it — reads as a "waiting for input" indicator, which mirrors
 * what await_human() does.
 */

import { cn } from "@/lib/utils";

export function LogoMark({
	size = 20,
	className,
}: {
	size?: number;
	className?: string;
}) {
	return (
		<svg
			width={size}
			height={size}
			viewBox="0 0 24 24"
			fill="none"
			role="img"
			aria-label="awaithumans"
			className={cn("shrink-0", className)}
		>
			<rect
				x="3"
				y="3"
				width="18"
				height="18"
				rx="5"
				stroke="currentColor"
				strokeOpacity="0.35"
				strokeWidth="1.5"
			/>
			<circle cx="12" cy="12" r="3.5" className="fill-brand">
				<animate
					attributeName="opacity"
					values="1;0.25;1"
					dur="2s"
					repeatCount="indefinite"
				/>
			</circle>
		</svg>
	);
}

export function Wordmark({
	size = "md",
	className,
}: {
	size?: "sm" | "md";
	className?: string;
}) {
	return (
		<div className={cn("flex items-center gap-2.5", className)}>
			<LogoMark size={size === "sm" ? 16 : 20} className="text-fg" />
			<span
				className={cn(
					"font-mono font-semibold tracking-tight text-fg",
					size === "sm" ? "text-sm" : "text-base",
				)}
			>
				awaithumans
			</span>
		</div>
	);
}
