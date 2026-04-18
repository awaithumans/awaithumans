"use client";

import { Mail, Plus, X } from "lucide-react";
import { useCallback, useEffect, useState } from "react";

import { TerminalSpinner } from "@/components/terminal-spinner";
import {
	createEmailIdentity,
	deleteEmailIdentity,
	fetchEmailIdentities,
	type CreateEmailIdentityRequest,
	type EmailIdentity,
	type EmailTransport,
} from "@/lib/server";
import { cn } from "@/lib/utils";
import { DestructiveInlineButton } from "./inline-confirm";
import { SettingsSection } from "./section";

const TRANSPORTS: EmailTransport[] = ["resend", "smtp", "logging", "noop"];

export function EmailIdentities() {
	const [identities, setIdentities] = useState<EmailIdentity[] | null>(null);
	const [error, setError] = useState<string | null>(null);
	const [showForm, setShowForm] = useState(false);
	const [deletingId, setDeletingId] = useState<string | null>(null);

	const load = useCallback(async () => {
		try {
			const list = await fetchEmailIdentities();
			setIdentities(list);
			setError(null);
		} catch (err) {
			setError(err instanceof Error ? err.message : "Failed to load");
		}
	}, []);

	useEffect(() => {
		load();
	}, [load]);

	const handleDelete = async (id: string) => {
		setDeletingId(id);
		try {
			await deleteEmailIdentity(id);
			await load();
		} catch (err) {
			setError(err instanceof Error ? err.message : "Delete failed");
		} finally {
			setDeletingId(null);
		}
	};

	return (
		<SettingsSection
			icon={Mail}
			title="Email sender identities"
			description={'Per-team sender profiles referenced as notify="email+<id>:user@example.com".'}
			action={
				!showForm && (
					<button
						type="button"
						onClick={() => setShowForm(true)}
						className="inline-flex items-center gap-1.5 px-3 py-1.5 border border-brand/30 text-brand hover:bg-brand/5 rounded-md text-xs font-medium transition-colors"
					>
						<Plus size={13} />
						Add identity
					</button>
				)
			}
		>
			{showForm && (
				<IdentityForm
					onCancel={() => setShowForm(false)}
					onSaved={async () => {
						setShowForm(false);
						await load();
					}}
					onError={setError}
				/>
			)}

			{error && (
				<div className="px-5 py-3 text-red-400 text-xs border-b border-red-400/20 bg-red-400/5">
					{error}
				</div>
			)}

			{/* When the endpoint errors (e.g. admin token not set → 503),
			    `identities` stays null forever. The error banner above
			    tells the story — don't also pin a perma-spinner. */}
			{error ? null : identities === null ? (
				<div className="px-5 py-4">
					<TerminalSpinner label="listing identities" />
				</div>
			) : identities.length === 0 && !showForm ? (
				<div className="px-5 py-6 text-center text-white/35 text-sm">
					No sender identities configured.
				</div>
			) : (
				<ul className="divide-y divide-white/5">
					{identities.map((i) => (
						<li
							key={i.id}
							className="px-5 py-3 flex items-center justify-between gap-4"
						>
							<div className="min-w-0">
								<div className="text-sm font-medium truncate">
									{i.display_name}
								</div>
								<div className="text-white/40 text-xs truncate">
									<span className="font-mono">{i.id}</span> ·{" "}
									{i.from_name ? `${i.from_name} ` : ""}
									{`<${i.from_email}>`}
								</div>
								<div className="flex items-center gap-2 mt-1">
									<span className="text-[10px] font-mono uppercase tracking-wider text-brand">
										{i.transport}
									</span>
									{i.verified ? (
										<span className="text-[10px] font-mono text-white/40">
											verified
										</span>
									) : (
										<span className="text-[10px] font-mono text-yellow-400/70">
											unverified
										</span>
									)}
								</div>
							</div>
							<DestructiveInlineButton
								label="Delete"
								armedLabel="Yes, delete"
								busy={deletingId === i.id}
								onConfirm={() => handleDelete(i.id)}
							/>
						</li>
					))}
				</ul>
			)}
		</SettingsSection>
	);
}

function IdentityForm({
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
				<h3 className="text-xs font-semibold text-white/70 uppercase tracking-wider">
					New identity
				</h3>
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
				<FormField label="ID" hint="URL-safe slug, e.g. acme-prod">
					<input
						required
						value={id}
						onChange={(e) => setId(e.target.value)}
						className={inputClass}
						placeholder="acme-prod"
					/>
				</FormField>
				<FormField label="Display name">
					<input
						required
						value={displayName}
						onChange={(e) => setDisplayName(e.target.value)}
						className={inputClass}
						placeholder="Acme Notifications"
					/>
				</FormField>
				<FormField label="From email">
					<input
						required
						type="email"
						value={fromEmail}
						onChange={(e) => setFromEmail(e.target.value)}
						className={inputClass}
						placeholder="notifications@acme.com"
					/>
				</FormField>
				<FormField label="From name (optional)">
					<input
						value={fromName}
						onChange={(e) => setFromName(e.target.value)}
						className={inputClass}
						placeholder="Acme Tasks"
					/>
				</FormField>
				<FormField label="Reply-to (optional)">
					<input
						type="email"
						value={replyTo}
						onChange={(e) => setReplyTo(e.target.value)}
						className={inputClass}
						placeholder="support@acme.com"
					/>
				</FormField>
				<FormField label="Transport">
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
				</FormField>
				<FormField
					label="Transport config (JSON)"
					hint={
						transport === "resend"
							? '{"api_key": "re_…"}'
							: transport === "smtp"
								? '{"host": "smtp.…", "port": 587, "user": "…", "password": "…"}'
								: "{} for logging / noop"
					}
					wide
				>
					<textarea
						value={transportConfigText}
						onChange={(e) => setTransportConfigText(e.target.value)}
						rows={3}
						className={cn(inputClass, "font-mono")}
					/>
				</FormField>
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

const inputClass =
	"w-full bg-white/5 border border-white/10 rounded-md px-2.5 py-1.5 text-xs placeholder:text-white/20 focus:outline-none focus:border-brand/40";

function FormField({
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
			<span className="text-[10px] font-medium text-white/50 uppercase tracking-wider mb-1 block">
				{label}
			</span>
			{children}
			{hint && <span className="text-[10px] text-white/30 mt-1 block">{hint}</span>}
		</label>
	);
}
