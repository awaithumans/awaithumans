"use client";

import { Check, Copy } from "lucide-react";
import { useState } from "react";

import { cn } from "@/lib/utils";

/**
 * "Copy" button that flips to a "copied" affirmation for ~1.5s
 * after a successful clipboard write. Used wherever the dashboard
 * shows a code snippet the operator should drop into a terminal or
 * editor.
 *
 * Silent on failure: if `navigator.clipboard` is unavailable
 * (insecure context, missing permissions) we just don't change the
 * UI — better than throwing an alert at someone whose paste-buffer
 * is fine via right-click.
 */
export function CopyButton({
	code,
	className,
}: {
	code: string;
	className?: string;
}) {
	const [copied, setCopied] = useState(false);

	const copy = async () => {
		try {
			await navigator.clipboard.writeText(code);
			setCopied(true);
			setTimeout(() => setCopied(false), 1500);
		} catch {
			// Clipboard API blocked (insecure context); fall through silently.
		}
	};

	return (
		<button
			type="button"
			onClick={copy}
			className={cn(
				"inline-flex items-center gap-1.5 text-[11px] font-mono px-2 py-1 rounded transition-colors",
				copied
					? "text-brand bg-brand/5"
					: "text-white/40 hover:text-white hover:bg-white/5",
				className,
			)}
			aria-label={copied ? "Copied" : "Copy code"}
		>
			{copied ? (
				<>
					<Check size={11} />
					copied
				</>
			) : (
				<>
					<Copy size={11} />
					copy
				</>
			)}
		</button>
	);
}
