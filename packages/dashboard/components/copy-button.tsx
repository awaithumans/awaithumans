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
 * Robust against the two failures we've seen in the wild:
 *   1. Parent <tr>/<div> with an `onClick` (e.g. audit row navigation)
 *      stealing focus before the clipboard write lands — fixed by
 *      stopPropagation on the click.
 *   2. `navigator.clipboard` unavailable on Safari in some contexts
 *      (older versions, non-HTTPS without localhost exemption). Falls
 *      back to the legacy `document.execCommand("copy")` path via a
 *      hidden textarea so the button still works.
 *
 * Logs a console.warn on hard failure so the operator can see what
 * happened in devtools rather than thinking the button is broken.
 */
export function CopyButton({
	code,
	className,
}: {
	code: string;
	className?: string;
}) {
	const [copied, setCopied] = useState(false);

	const copy = async (e: React.MouseEvent<HTMLButtonElement>) => {
		// Defensive: a parent row/container may have its own onClick
		// (e.g. audit-log row → navigate to task). Without stopping
		// propagation, the row click can preempt the clipboard write.
		e.stopPropagation();
		e.preventDefault();

		const writeOk = await writeToClipboard(code);
		if (writeOk) {
			setCopied(true);
			setTimeout(() => setCopied(false), 1500);
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

async function writeToClipboard(text: string): Promise<boolean> {
	// Modern path. Localhost is a secure context per spec so this
	// should work for `awaithumans dev`, but `navigator.clipboard`
	// is still undefined in a few edge cases (older Safari, iframes
	// without `clipboard-write` permission).
	if (typeof navigator !== "undefined" && navigator.clipboard) {
		try {
			await navigator.clipboard.writeText(text);
			return true;
		} catch (err) {
			console.warn(
				"navigator.clipboard.writeText failed; falling back to execCommand:",
				err,
			);
		}
	}

	// Legacy fallback. Deprecated but still works everywhere.
	try {
		const ta = document.createElement("textarea");
		ta.value = text;
		ta.style.position = "fixed";
		ta.style.opacity = "0";
		ta.style.pointerEvents = "none";
		document.body.appendChild(ta);
		ta.focus();
		ta.select();
		const ok = document.execCommand("copy");
		document.body.removeChild(ta);
		if (!ok) {
			console.warn("document.execCommand('copy') returned false.");
		}
		return ok;
	} catch (err) {
		console.warn("Clipboard fallback failed:", err);
		return false;
	}
}
