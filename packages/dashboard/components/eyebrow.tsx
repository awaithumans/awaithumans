import type { ElementType } from "react";

import { cn } from "@/lib/utils";

/**
 * Small-caps section label — the "eyebrow" you'd expect above a
 * heading. Used across the dashboard for column headers, micro labels
 * above big metrics, section titles, and `dt` in config lists.
 *
 * All-caps + wide tracking is the one typography recipe we repeat
 * intentionally — Stripe / Linear / Vercel all lean on it for reasons
 * that actually apply here (mono body text benefits from a distinct
 * uppercase register so labels don't blur into content).
 */
export function Eyebrow({
	as: Tag = "span",
	size = "sm",
	tone = "muted",
	mono,
	weight = "medium",
	className,
	children,
}: {
	as?: ElementType;
	/** micro = 10px; sm = 12px (default); md = 14px for section headings. */
	size?: "micro" | "sm" | "md";
	/** Colour step. default `muted`; `brand` for emphasis; `subtle` / `bright` for the edges. */
	tone?: "muted" | "brand" | "subtle" | "bright";
	/** Use JetBrains Mono explicitly (body font is already mono project-wide,
	 *  but some call sites render inline text that shouldn't absorb it). */
	mono?: boolean;
	weight?: "normal" | "medium" | "semibold";
	className?: string;
	children: React.ReactNode;
}) {
	const toneClass =
		tone === "brand"
			? "text-brand"
			: tone === "subtle"
				? "text-white/30"
				: tone === "bright"
					? "text-white/70"
					: "text-muted";

	const weightClass =
		weight === "semibold"
			? "font-semibold"
			: weight === "medium"
				? "font-medium"
				: "";

	return (
		<Tag
			className={cn(
				"uppercase tracking-wider",
				size === "micro"
					? "text-[10px]"
					: size === "md"
						? "text-sm"
						: "text-xs",
				toneClass,
				weightClass,
				mono && "font-mono",
				className,
			)}
		>
			{children}
		</Tag>
	);
}
