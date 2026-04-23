/**
 * Shell-style empty state.
 *
 * Used on Tasks / Audit when there's no data. Renders like a terminal
 * session: a `$` prompt, a comment explaining what's going on, and —
 * when the emptiness is a "you haven't used the product yet" moment —
 * a copyable code snippet that makes the thing appear.
 *
 * The aesthetic mirrors the CLI: monospace, dim-by-default, brand-green
 * only on keywords worth looking at. This is the product's "first
 * screen" for a lot of people — make it feel intentional.
 */

import { Check, Copy } from "lucide-react";
import { useState } from "react";

import { Eyebrow } from "@/components/eyebrow";
import { cn } from "@/lib/utils";

type Language = "python" | "typescript" | "bash";

/** Snippet prop shape:
 *   - single string     → one code block, labeled with `language` (legacy)
 *   - record-of-strings → one code block per key, rendered with a tab toggle */
type SnippetProp = string | Partial<Record<Language, string>>;

export function ShellEmptyState({
	heading,
	note,
	snippet,
	language = "python",
	className,
}: {
	/** Short line shown after the `$` prompt — the "command" that was run. */
	heading: string;
	/** Optional second line. Rendered like a shell comment (`# ...`). */
	note?: string;
	/**
	 * Optional code the reader can copy to unblock themselves. Pass a
	 * string for a single language, or `{ python: "...", typescript: "..." }`
	 * to render a language-toggle tab above the code block.
	 */
	snippet?: SnippetProp;
	/** Only used when `snippet` is a string. Ignored for the object form. */
	language?: Language;
	className?: string;
}) {
	return (
		<div
			className={cn(
				"border border-white/10 rounded-lg bg-white/[0.015] overflow-hidden",
				className,
			)}
		>
			{/* Shell line */}
			<div className="px-5 py-4 font-mono text-sm border-b border-white/5">
				<span className="text-white/30 mr-2">$</span>
				<span className="text-fg">{heading}</span>
			</div>
			{note && (
				<div className="px-5 py-3 font-mono text-xs text-white/40">
					<span className="text-white/25 mr-1.5">#</span>
					{note}
				</div>
			)}
			{snippet && <SnippetPanel snippet={snippet} defaultLanguage={language} />}
		</div>
	);
}

function SnippetPanel({
	snippet,
	defaultLanguage,
}: {
	snippet: SnippetProp;
	defaultLanguage: Language;
}) {
	if (typeof snippet === "string") {
		return <CodeSnippet code={snippet} language={defaultLanguage} />;
	}

	// Multi-language: render the first available as default and add a toggle.
	const entries = (Object.entries(snippet) as [Language, string][])
		.filter(([, v]) => typeof v === "string");
	if (entries.length === 0) return null;
	if (entries.length === 1) {
		const [lang, code] = entries[0];
		return <CodeSnippet code={code} language={lang} />;
	}
	return <MultiLanguageSnippet entries={entries} />;
}

function MultiLanguageSnippet({
	entries,
}: {
	entries: [Language, string][];
}) {
	const [active, setActive] = useState<Language>(entries[0][0]);
	const activeEntry = entries.find(([l]) => l === active) ?? entries[0];
	const code = activeEntry[1];

	return (
		<div className="relative bg-bg/40 border-t border-white/5">
			<div className="flex items-center justify-between px-5 py-2 border-b border-white/5">
				<div className="inline-flex gap-1">
					{entries.map(([lang]) => (
						<button
							key={lang}
							type="button"
							onClick={() => setActive(lang)}
							className={cn(
								"text-[10px] uppercase tracking-wider font-mono px-2 py-1 rounded transition-colors",
								active === lang
									? "bg-brand/10 text-brand"
									: "text-white/40 hover:text-white/70",
							)}
						>
							{lang}
						</button>
					))}
				</div>
				<CopyButton code={code} />
			</div>
			<pre className="px-5 py-4 text-xs font-mono text-fg/80 overflow-x-auto leading-relaxed">
				<code>{code}</code>
			</pre>
		</div>
	);
}

function CodeSnippet({
	code,
	language,
}: {
	code: string;
	language: string;
}) {
	return (
		<div className="relative bg-bg/40 border-t border-white/5">
			<div className="flex items-center justify-between px-5 py-2 border-b border-white/5">
				<Eyebrow size="micro" tone="subtle" mono>
					{language}
				</Eyebrow>
				<CopyButton code={code} />
			</div>
			<pre className="px-5 py-4 text-xs font-mono text-fg/80 overflow-x-auto leading-relaxed">
				<code>{code}</code>
			</pre>
		</div>
	);
}

function CopyButton({ code }: { code: string }) {
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
