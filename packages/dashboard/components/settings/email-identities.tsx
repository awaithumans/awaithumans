"use client";

import { Mail, Plus } from "lucide-react";
import { useCallback, useEffect, useState } from "react";

import { Eyebrow } from "@/components/eyebrow";
import { TerminalSpinner } from "@/components/terminal-spinner";
import {
	deleteEmailIdentity,
	fetchEmailIdentities,
	type EmailIdentity,
} from "@/lib/server";
import { EmailIdentityForm } from "./email-identity-form";
import { DestructiveInlineButton } from "./inline-confirm";
import { SettingsSection } from "./section";

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
			description={
				'Per-team sender profiles. Reference as notify="email+<id>:user@example.com" — or bare "email:user@example.com" when this is your only identity.'
			}
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
				<EmailIdentityForm
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
						<IdentityRow
							key={i.id}
							identity={i}
							deleting={deletingId === i.id}
							onDelete={() => handleDelete(i.id)}
						/>
					))}
				</ul>
			)}
		</SettingsSection>
	);
}

function IdentityRow({
	identity: i,
	deleting,
	onDelete,
}: {
	identity: EmailIdentity;
	deleting: boolean;
	onDelete: () => void;
}) {
	return (
		<li className="px-5 py-3 flex items-center justify-between gap-4">
			<div className="min-w-0">
				<div className="text-sm font-medium truncate">{i.display_name}</div>
				<div className="text-white/40 text-xs truncate">
					<span className="font-mono">{i.id}</span> ·{" "}
					{i.from_name ? `${i.from_name} ` : ""}
					{`<${i.from_email}>`}
				</div>
				<div className="flex items-center gap-2 mt-1">
					<Eyebrow size="micro" tone="brand" mono>
						{i.transport}
					</Eyebrow>
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
				busy={deleting}
				onConfirm={onDelete}
			/>
		</li>
	);
}
