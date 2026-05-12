"use client";

import { X } from "lucide-react";
import { useState } from "react";

import { Eyebrow } from "@/components/eyebrow";
import {
	createEmailIdentity,
	type CreateEmailIdentityRequest,
	type EmailTransport,
} from "@/lib/server";
import { cn } from "@/lib/utils";

const TRANSPORTS: EmailTransport[] = ["resend", "smtp", "logging", "noop"];

// Shared input styling for every field in the form. Defined once so
// tweaks land everywhere consistently.
const inputClass =
	"w-full bg-white/5 border border-white/10 rounded-md px-2.5 py-1.5 text-xs placeholder:text-white/20 focus:outline-none focus:border-brand/40";

const TRANSPORT_CONFIG_HINT: Record<EmailTransport, string> = {
	resend: '{"api_key": "re_…"}',
	smtp: '587/STARTTLS: {"host":"smtp.…","port":587,"username":"…","password":"…"} · 465/implicit TLS: add "use_tls": true',
	logging: "{} for logging / noop",
	noop: "{} for logging / noop",
};

/**
 * Inline "create identity" form. Rendered inside the EmailIdentities
 * section when the operator clicks "Add identity". Owns its own local
 * state; calls `onSaved` after a successful POST so the parent can
 * reload the list, or `onError` to surface a banner.
 */
export function EmailIdentityForm({
	onCancel,
	onSaved,
	onError,
}: {
	onCancel: () => void;
	onSaved: () => Promise<void>;
	onError: (msg: string) => void;
}) {
	const [id, setId] = useState("");
	const [displayName, setDisplayName] = useState("");
	const [fromEmail, setFromEmail] = useState("");
	const [fromName, setFromName] = useState("");
	const [replyTo, setReplyTo] = useState("");
	const [transport, setTransport] = useState<EmailTransport>("logging");
	const [transportConfigText, setTransportConfigText] = useState("{}");
	const [submitting, setSubmitting] = useState(false);

	const handleSubmit = async (e: React.FormEvent) => {
		e.preventDefault();
		setSubmitting(true);
		try {
			// Blank textarea → empty config. Otherwise JSON-parse; a bad
			// parse throws synchronously and surfaces via onError below.
			const config =
				transportConfigText.trim() === ""
					? {}
					: (JSON.parse(transportConfigText) as Record<string, unknown>);
			const body: CreateEmailIdentityRequest = {
				id,
				display_name: displayName,
				from_email: fromEmail,
				transport,
				transport_config: config,
				...(fromName ? { from_name: fromName } : {}),
				...(replyTo ? { reply_to: replyTo } : {}),
			};
			await createEmailIdentity(body);
			await onSaved();
		} catch (err) {
			onError(err instanceof Error ? err.message : "Create failed");
		} finally {
			setSubmitting(false);
		}
	};

	return (
		<form
			onSubmit={handleSubmit}
			className="px-5 py-4 border-b border-white/5 bg-white/[0.02]"
		>
			<div className="flex items-center justify-between mb-3">
				<Eyebrow as="h3" weight="semibold" className="text-white/70">
					New identity
				</Eyebrow>
				<button
					type="button"
					onClick={onCancel}
					className="text-white/40 hover:text-white"
					aria-label="Cancel"
				>
					<X size={14} />
				</button>
			</div>

			<div className="grid grid-cols-2 gap-3">
				<Field label="ID" hint="URL-safe slug, e.g. acme-prod">
					<input
						required
						value={id}
						onChange={(e) => setId(e.target.value)}
						className={inputClass}
						placeholder="acme-prod"
					/>
				</Field>
				<Field label="Display name">
					<input
						required
						value={displayName}
						onChange={(e) => setDisplayName(e.target.value)}
						className={inputClass}
						placeholder="Acme Notifications"
					/>
				</Field>
				<Field label="From email">
					<input
						required
						type="email"
						value={fromEmail}
						onChange={(e) => setFromEmail(e.target.value)}
						className={inputClass}
						placeholder="notifications@acme.com"
					/>
				</Field>
				<Field label="From name (optional)">
					<input
						value={fromName}
						onChange={(e) => setFromName(e.target.value)}
						className={inputClass}
						placeholder="Acme Tasks"
					/>
				</Field>
				<Field label="Reply-to (optional)">
					<input
						type="email"
						value={replyTo}
						onChange={(e) => setReplyTo(e.target.value)}
						className={inputClass}
						placeholder="support@acme.com"
					/>
				</Field>
				<Field label="Transport">
					<select
						value={transport}
						onChange={(e) => setTransport(e.target.value as EmailTransport)}
						className={inputClass}
					>
						{TRANSPORTS.map((t) => (
							<option key={t} value={t}>
								{t}
							</option>
						))}
					</select>
				</Field>
				<Field
					label="Transport config (JSON)"
					hint={TRANSPORT_CONFIG_HINT[transport]}
					wide
				>
					<textarea
						value={transportConfigText}
						onChange={(e) => setTransportConfigText(e.target.value)}
						rows={3}
						className={cn(inputClass, "font-mono")}
					/>
				</Field>
			</div>

			<div className="flex justify-end gap-2 mt-4">
				<button
					type="button"
					onClick={onCancel}
					className="px-3 py-1.5 text-xs text-white/50 hover:text-white transition-colors"
				>
					Cancel
				</button>
				<button
					type="submit"
					disabled={submitting}
					className="px-4 py-1.5 bg-brand text-black font-semibold text-xs rounded-md hover:bg-brand/90 disabled:opacity-40 transition-colors"
				>
					{submitting ? "Creating…" : "Create identity"}
				</button>
			</div>
		</form>
	);
}

function Field({
	label,
	children,
	hint,
	wide,
}: {
	label: string;
	children: React.ReactNode;
	hint?: string;
	wide?: boolean;
}) {
	return (
		<label className={cn("block", wide && "col-span-2")}>
			<Eyebrow size="micro" className="block text-white/50 mb-1">
				{label}
			</Eyebrow>
			{children}
			{hint && (
				<span className="text-[10px] text-white/30 mt-1 block">{hint}</span>
			)}
		</label>
	);
}
