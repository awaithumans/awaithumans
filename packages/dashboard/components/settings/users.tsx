"use client";

import { Pencil, Plus, Users as UsersIcon } from "lucide-react";
import { useCallback, useEffect, useState } from "react";

import { Eyebrow } from "@/components/eyebrow";
import { TerminalSpinner } from "@/components/terminal-spinner";
import { deleteUser, fetchUsers, type User } from "@/lib/server";
import { DestructiveInlineButton } from "./inline-confirm";
import { SettingsSection } from "./section";
import { UserForm } from "./user-form";

export function UsersManagement() {
	const [users, setUsers] = useState<User[] | null>(null);
	const [error, setError] = useState<string | null>(null);
	const [adding, setAdding] = useState(false);
	const [editing, setEditing] = useState<User | null>(null);
	const [deletingId, setDeletingId] = useState<string | null>(null);

	const load = useCallback(async () => {
		try {
			const list = await fetchUsers();
			setUsers(list);
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
			await deleteUser(id);
			await load();
		} catch (err) {
			setError(err instanceof Error ? err.message : "Delete failed");
		} finally {
			setDeletingId(null);
		}
	};

	const showingForm = adding || editing !== null;

	return (
		<SettingsSection
			icon={UsersIcon}
			title="Users"
			description="People who receive tasks (email / Slack) or log into the dashboard. Operators can manage other users from here."
			action={
				!showingForm && (
					<button
						type="button"
						onClick={() => setAdding(true)}
						className="inline-flex items-center gap-1.5 px-3 py-1.5 border border-brand/30 text-brand hover:bg-brand/5 rounded-md text-xs font-medium transition-colors"
					>
						<Plus size={13} />
						Add user
					</button>
				)
			}
		>
			{adding && (
				<UserForm
					editing={null}
					onCancel={() => setAdding(false)}
					onSaved={async () => {
						setAdding(false);
						await load();
					}}
					onError={setError}
				/>
			)}

			{editing && (
				<UserForm
					editing={editing}
					onCancel={() => setEditing(null)}
					onSaved={async () => {
						setEditing(null);
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

			{error ? null : users === null ? (
				<div className="px-5 py-4">
					<TerminalSpinner label="listing users" />
				</div>
			) : users.length === 0 && !showingForm ? (
				<div className="px-5 py-6 text-center text-white/35 text-sm">
					No users yet. Add your first to route tasks by role.
				</div>
			) : (
				<ul className="divide-y divide-white/5">
					{users.map((u) => (
						<UserRow
							key={u.id}
							user={u}
							deleting={deletingId === u.id}
							onEdit={() => setEditing(u)}
							onDelete={() => handleDelete(u.id)}
						/>
					))}
				</ul>
			)}
		</SettingsSection>
	);
}

function UserRow({
	user: u,
	deleting,
	onEdit,
	onDelete,
}: {
	user: User;
	deleting: boolean;
	onEdit: () => void;
	onDelete: () => void;
}) {
	// Headline fallback chain. The row ID (last resort) is a 32-char
	// hex string — it's never useful to humans, so we exhaust every
	// human-friendly option first: the operator's display name, then
	// their email, then a recognisable Slack reference like
	// `@U_ALICE`. Only if all of those are missing do we land on the
	// raw row ID (and even then the addressLine below repeats the
	// Slack ID so the operator can see what's going on).
	const primaryLabel =
		u.display_name ||
		u.email ||
		(u.slack_user_id ? `@${u.slack_user_id}` : null) ||
		u.id;
	const addressLine = [
		u.email,
		u.slack_user_id ? `slack:${u.slack_user_id}` : null,
	]
		.filter(Boolean)
		.join(" · ");

	const attrs = [u.role, u.access_level, u.pool].filter(Boolean) as string[];

	return (
		<li className="px-5 py-3 flex items-center justify-between gap-4">
			<div className="min-w-0 flex-1">
				<div className="flex items-center gap-2">
					<div className="text-sm font-medium truncate">{primaryLabel}</div>
					{u.is_operator && (
						<Eyebrow size="micro" tone="brand" mono>
							operator
						</Eyebrow>
					)}
					{!u.active && (
						<Eyebrow size="micro" tone="muted" mono>
							inactive
						</Eyebrow>
					)}
				</div>
				<div className="text-white/40 text-xs truncate font-mono">
					{addressLine || u.id}
				</div>
				{attrs.length > 0 && (
					<div className="flex items-center gap-1.5 mt-1">
						{attrs.map((a) => (
							<span
								key={a}
								className="text-[10px] font-mono text-white/40 px-1.5 py-0.5 rounded bg-white/5"
							>
								{a}
							</span>
						))}
					</div>
				)}
				{u.last_assigned_at && (
					<div className="text-[10px] text-white/30 mt-1">
						Last assigned {new Date(u.last_assigned_at).toLocaleString()}
					</div>
				)}
			</div>
			<div className="flex items-center gap-2">
				<button
					type="button"
					onClick={onEdit}
					className="p-1.5 text-white/50 hover:text-white transition-colors"
					aria-label="Edit"
				>
					<Pencil size={13} />
				</button>
				<DestructiveInlineButton
					label="Delete"
					armedLabel="Yes, delete"
					busy={deleting}
					onConfirm={onDelete}
				/>
			</div>
		</li>
	);
}
