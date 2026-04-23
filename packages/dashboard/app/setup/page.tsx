"use client";

import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";

import { LogoMark } from "@/components/logo";
import { TerminalSpinner } from "@/components/terminal-spinner";
import { ApiError, createFirstOperator, fetchSetupStatus } from "@/lib/server";
import { cn } from "@/lib/utils";

/**
 * First-run setup wizard. Two-step flow:
 *
 * 1. Create operator account (token + email + password)
 * 2. Show a "send your first task" onboarding panel with Python /
 *    TypeScript code tabs, then a link to the dashboard
 *
 * The code examples mirror `examples/quickstart/` and
 * `examples/quickstart-ts/`. Keep them in sync — if the SDK shape
 * changes, update all three.
 */
export default function SetupPage() {
	return (
		<Suspense
			fallback={
				<div className="min-h-screen flex items-center justify-center">
					<TerminalSpinner label="checking server" />
				</div>
			}
		>
			<SetupPageInner />
		</Suspense>
	);
}

type Lang = "python" | "typescript";

function SetupPageInner() {
	const router = useRouter();
	const params = useSearchParams();

	const [token, setToken] = useState(() => params.get("token") ?? "");
	const [email, setEmail] = useState("");
	const [displayName, setDisplayName] = useState("");
	const [password, setPassword] = useState("");
	const [confirm, setConfirm] = useState("");

	const [submitting, setSubmitting] = useState(false);
	const [error, setError] = useState<string | null>(null);
	const [state, setState] = useState<
		"checking" | "ready" | "already-done" | "created" | "unreachable"
	>("checking");

	useEffect(() => {
		(async () => {
			try {
				const status = await fetchSetupStatus();
				if (!status.needs_setup) {
					setState("already-done");
				} else {
					setState("ready");
				}
			} catch {
				setState("unreachable");
			}
		})();
	}, []);

	const handleSubmit = async (e: React.FormEvent) => {
		e.preventDefault();
		setError(null);
		if (password !== confirm) {
			setError("Passwords don't match.");
			return;
		}
		if (password.length < 8) {
			setError("Password must be at least 8 characters.");
			return;
		}

		setSubmitting(true);
		try {
			await createFirstOperator({
				token,
				email,
				password,
				display_name: displayName || undefined,
			});
			// Server sets the session cookie on 201 — show onboarding step.
			setState("created");
		} catch (err) {
			// Match on typed errors instead of string-sniffing status
			// codes (same brittle pattern we removed from /login).
			if (err instanceof ApiError && err.status === 403) {
				setError(
					"Setup token rejected. Check the server log for the latest token.",
				);
			} else if (err instanceof ApiError && err.status === 409) {
				setError("Setup is already complete. Please sign in instead.");
				setState("already-done");
			} else if (err instanceof TypeError) {
				setError("Can't reach the server. Is `awaithumans dev` still running?");
			} else if (err instanceof Error) {
				// ApiError with other statuses, or anything else that
				// already carries a readable message (server message
				// via ApiError, validation errors, etc.) — show it
				// verbatim, no "Setup failed:" prefix muddying it.
				setError(err.message);
			} else {
				setError("Setup failed. Please try again.");
			}
		} finally {
			setSubmitting(false);
		}
	};

	if (state === "checking") {
		return (
			<div className="min-h-screen flex items-center justify-center">
				<TerminalSpinner label="checking server" />
			</div>
		);
	}

	if (state === "already-done") {
		return (
			<Shell title="Setup already complete">
				<p className="text-white/60 text-sm mb-4">
					This server already has an operator account. Sign in with those
					credentials.
				</p>
				<a
					href="/login"
					className="block w-full px-4 py-2.5 bg-brand text-black font-semibold text-sm rounded-md text-center hover:bg-brand/90"
				>
					Go to sign in
				</a>
			</Shell>
		);
	}

	if (state === "unreachable") {
		return (
			<Shell title="Server unreachable">
				<p className="text-white/60 text-sm">
					Can't reach <code>/api/setup/status</code>. Make sure{" "}
					<code>awaithumans dev</code> is running and refresh.
				</p>
			</Shell>
		);
	}

	if (state === "created") {
		return <OnboardingPanel onContinue={() => router.replace("/")} />;
	}

	return (
		<Shell title="First-run setup">
			<p className="text-white/40 text-xs mb-5">
				Create the initial operator account. The setup token was printed to
				the server log when the process started — paste it below.
			</p>

			<form onSubmit={handleSubmit} className="space-y-4">
				<Field
					label="Setup token"
					value={token}
					onChange={setToken}
					disabled={submitting}
					autoFocus={!token}
					type="text"
				/>
				<Field
					label="Email"
					type="email"
					value={email}
					onChange={setEmail}
					disabled={submitting}
					autoFocus={!!token && !email}
				/>
				<Field
					label="Display name (optional)"
					value={displayName}
					onChange={setDisplayName}
					disabled={submitting}
				/>
				<Field
					label="Password"
					type="password"
					value={password}
					onChange={setPassword}
					disabled={submitting}
				/>
				<Field
					label="Confirm password"
					type="password"
					value={confirm}
					onChange={setConfirm}
					disabled={submitting}
				/>

				{error && (
					<div className="text-red-400 text-xs border border-red-400/30 bg-red-400/5 rounded-md px-3 py-2">
						{error}
					</div>
				)}

				<button
					type="submit"
					disabled={submitting || !token || !email || !password || !confirm}
					className="w-full px-4 py-2.5 bg-brand text-black font-semibold text-sm rounded-md hover:bg-brand/90 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
				>
					{submitting ? "Creating…" : "Create operator"}
				</button>
			</form>
		</Shell>
	);
}

// ─── Post-creation onboarding panel ─────────────────────────────────

function OnboardingPanel({ onContinue }: { onContinue: () => void }) {
	const [lang, setLang] = useState<Lang>("python");

	return (
		<div className="min-h-screen flex items-center justify-center px-6 py-12">
			<div className="w-full max-w-2xl">
				<div className="flex items-center gap-2.5 mb-8 justify-center">
					<LogoMark size={24} className="text-fg" />
					<span className="font-mono font-semibold tracking-tight text-base">
						awaithumans
					</span>
				</div>

				<div className="border border-white/10 rounded-lg p-6 bg-white/[0.02]">
					<div className="flex items-center gap-2 mb-1">
						<span className="text-brand">✓</span>
						<h1 className="text-lg font-semibold">Operator created</h1>
					</div>
					<p className="text-white/40 text-xs mb-6">
						You're signed in. Try sending your first task from an agent.
					</p>

					<LanguageTabs lang={lang} onChange={setLang} />

					<div className="mt-4 space-y-4">
						<div>
							<Label>1. Install</Label>
							<CodeBlock>
								{lang === "python"
									? "pip install awaithumans"
									: "npm install awaithumans zod"}
							</CodeBlock>
						</div>

						<div>
							<Label>
								2. Save as{" "}
								<span className="text-white/60 font-mono">
									{lang === "python" ? "refund.py" : "refund.ts"}
								</span>
							</Label>
							<CodeBlock multiline>
								{lang === "python" ? PYTHON_EXAMPLE : TYPESCRIPT_EXAMPLE}
							</CodeBlock>
						</div>

						<div>
							<Label>3. Run</Label>
							<CodeBlock>
								{lang === "python" ? "python refund.py" : "npx tsx refund.ts"}
							</CodeBlock>
						</div>
					</div>

					<div className="mt-6 pt-5 border-t border-white/5">
						<p className="text-white/40 text-xs mb-3">
							A task will land in the queue. Open it, submit the form, and
							your agent unblocks with the typed response.
						</p>
						<button
							type="button"
							onClick={onContinue}
							className="w-full px-4 py-2.5 bg-brand text-black font-semibold text-sm rounded-md hover:bg-brand/90 transition-colors"
						>
							Go to dashboard →
						</button>
					</div>
				</div>

				<p className="text-center text-white/25 text-xs mt-6">
					Need Slack / email notifications? Configure channels in{" "}
					<a href="/settings" className="text-brand/80 hover:text-brand">
						Settings
					</a>
					.
				</p>
			</div>
		</div>
	);
}

function LanguageTabs({
	lang,
	onChange,
}: {
	lang: Lang;
	onChange: (l: Lang) => void;
}) {
	return (
		<div className="inline-flex border border-white/10 rounded-md overflow-hidden">
			{(["python", "typescript"] as const).map((option) => (
				<button
					key={option}
					type="button"
					onClick={() => onChange(option)}
					className={cn(
						"px-3 py-1.5 text-xs font-medium transition-colors",
						lang === option
							? "bg-brand text-black"
							: "text-white/50 hover:text-white hover:bg-white/5",
					)}
				>
					{option === "python" ? "Python" : "TypeScript"}
				</button>
			))}
		</div>
	);
}

function Label({ children }: { children: React.ReactNode }) {
	return (
		<div className="text-[10px] uppercase tracking-wider text-white/40 font-medium mb-1.5">
			{children}
		</div>
	);
}

function CodeBlock({
	children,
	multiline,
}: {
	children: React.ReactNode;
	multiline?: boolean;
}) {
	return (
		<pre
			className={cn(
				"bg-black/40 border border-white/10 rounded-md px-3 py-2.5 text-xs overflow-x-auto font-mono text-white/80",
				multiline ? "leading-relaxed" : "",
			)}
		>
			{!multiline && <span className="text-white/30 mr-2">$</span>}
			<code>{children}</code>
		</pre>
	);
}

// ─── Example code (mirrors examples/quickstart{,-ts}/) ───────────────

const PYTHON_EXAMPLE = `from awaithumans import await_human_sync
from pydantic import BaseModel

class RefundRequest(BaseModel):
    order_id: str
    amount_usd: float

class Decision(BaseModel):
    approved: bool
    reason: str  # short-answer field — the reviewer explains their call

print("→ creating task — go to the dashboard to review and complete it")

decision = await_human_sync(
    task="Approve refund",
    payload_schema=RefundRequest,
    payload=RefundRequest(order_id="A-4721", amount_usd=180),
    response_schema=Decision,
    timeout_seconds=900,
)

verdict = "approved" if decision.approved else "rejected"
print(f"✓ Refund {verdict}. Reason: {decision.reason}")`;

const TYPESCRIPT_EXAMPLE = `import { awaitHuman } from "awaithumans";
import { z } from "zod";

const RefundRequest = z.object({
  orderId: z.string(),
  amountUsd: z.number(),
});

const Decision = z.object({
  approved: z.boolean(),
  // short-answer field — the reviewer explains their call
  reason: z.string(),
});

async function main() {
  console.log("→ creating task — go to the dashboard to review and complete it");

  const decision = await awaitHuman({
    task: "Approve refund",
    payloadSchema: RefundRequest,
    payload: { orderId: "A-4721", amountUsd: 180 },
    responseSchema: Decision,
    timeoutMs: 900_000,
  });

  const verdict = decision.approved ? "approved" : "rejected";
  console.log(\`✓ Refund \${verdict}. Reason: \${decision.reason}\`);
}

main();`;

// ─── Shared layout pieces ────────────────────────────────────────────

function Shell({ title, children }: { title: string; children: React.ReactNode }) {
	return (
		<div className="min-h-screen flex items-center justify-center px-6">
			<div className="w-full max-w-sm">
				<div className="flex items-center gap-2.5 mb-8 justify-center">
					<LogoMark size={24} className="text-fg" />
					<span className="font-mono font-semibold tracking-tight text-base">
						awaithumans
					</span>
				</div>
				<div className="border border-white/10 rounded-lg p-6 bg-white/[0.02]">
					<h1 className="text-lg font-semibold mb-1">{title}</h1>
					{children}
				</div>
			</div>
		</div>
	);
}

function Field({
	label,
	value,
	onChange,
	type = "text",
	autoFocus,
	disabled,
}: {
	label: string;
	value: string;
	onChange: (v: string) => void;
	type?: string;
	autoFocus?: boolean;
	disabled?: boolean;
}) {
	return (
		<label className="block">
			<span className="text-xs font-medium text-white/60 mb-1.5 block">
				{label}
			</span>
			<input
				type={type}
				value={value}
				onChange={(e) => onChange(e.target.value)}
				autoFocus={autoFocus}
				disabled={disabled}
				className="w-full bg-white/5 border border-white/10 rounded-md px-3 py-2 text-sm focus:outline-none focus:border-brand/40 disabled:opacity-40"
			/>
		</label>
	);
}
