"use client";

import { Check, Trash2, X } from "lucide-react";
import { useState } from "react";

import { cn } from "@/lib/utils";

/**
 * Destructive button with inline confirm.
 *
 * First click flips the button into an armed state with explicit
 * [cancel] [confirm] affordances. No modal, no `window.confirm()`.
 * Keeps the user in place, keeps the page keyboard-focusable, and
 * avoids the browser chrome we can't style.
 *
 * The armed state auto-resets after the parent's async action settles
 * (pass `busy` while the network call is in flight).
 */
export function DestructiveInlineButton({
	label = "Delete",
	armedLabel = "Confirm",
	onConfirm,
	busy,
	busyLabel = "Removing…",
	className,
}: {
	/** Shown in the idle state. */
	label?: string;
	/** Shown on the confirm button once the user has armed the action. */
	armedLabel?: string;
	onConfirm: () => void | Promise<void>;
	busy?: boolean;
	busyLabel?: string;
	className?: string;
}) {
	const [armed, setArmed] = useState(false);

	if (busy) {
		return (
			<span className="inline-flex items-center gap-1.5 text-xs text-muted px-2 py-1">
				<span className="inline-block w-1.5 h-1.5 rounded-full bg-red-400/60 motion-safe:animate-pulse" />
				{busyLabel}
			</span>
		);
	}

	if (!armed) {
		return (
			<button
				type="button"
				onClick={() => setArmed(true)}
				className={cn(
					"flex items-center gap-1.5 text-xs text-red-400/80 hover:text-red-400 transition-colors px-2 py-1 rounded-md hover:bg-red-400/5",
					className,
				)}
			>
				<Trash2 size={13} />
				{label}
			</button>
		);
	}

	return (
		<span className="inline-flex items-center gap-1 text-xs">
			<button
				type="button"
				onClick={() => setArmed(false)}
				className="flex items-center gap-1 px-2 py-1 rounded-md text-muted hover:text-fg hover:bg-white/5 transition-colors"
				aria-label="Cancel"
			>
				<X size={12} />
				cancel
			</button>
			<button
				type="button"
				onClick={async () => {
					try {
						await onConfirm();
					} finally {
						setArmed(false);
					}
				}}
				className="flex items-center gap-1 px-2 py-1 rounded-md bg-red-400/10 text-red-400 hover:bg-red-400/20 transition-colors font-medium"
			>
				<Check size={12} />
				{armedLabel}
			</button>
		</span>
	);
}
