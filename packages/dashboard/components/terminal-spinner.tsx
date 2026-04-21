/**
 * Terminal-style loading indicator — `$ <label>_` with a blinking cursor.
 *
 * Replaces every "Loading…" across the dashboard. The product ships a
 * primitive that makes agents await humans; the UI's "waiting" moments
 * deserve the same shell-prompt aesthetic the CLI has.
 *
 * The cursor animates via pure CSS (no JS, no layout thrash). Respects
 * prefers-reduced-motion — the blink is swapped for a static underscore.
 */

import { cn } from "@/lib/utils";

export function TerminalSpinner({
	label = "awaiting",
	className,
	size = "sm",
}: {
	/** Verb placed after the `$` prompt. Keep it short (one word is ideal). */
	label?: string;
	className?: string;
	size?: "sm" | "md";
}) {
	return (
		<span
			className={cn(
				"inline-flex items-baseline gap-1 font-mono text-white/50 tabular-nums",
				size === "md" ? "text-sm" : "text-xs",
				className,
			)}
			role="status"
			aria-label={`${label}…`}
		>
			<span className="text-white/30">$</span>
			<span>{label}</span>
			<BlinkingCursor />
		</span>
	);
}

function BlinkingCursor() {
	return (
		<span
			aria-hidden
			className={cn(
				"inline-block w-[0.6em] h-[1em] translate-y-[0.1em] bg-brand/80",
				// Blink at ~1.2Hz. Swap to a steady block for reduced-motion folks
				// so no one gets a strobe.
				"motion-safe:animate-[terminal-blink_1.1s_step-end_infinite]",
			)}
			style={{
				animationName: undefined, // class above handles it; keep style clean
			}}
		/>
	);
}
