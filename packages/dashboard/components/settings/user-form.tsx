"use client";

import { X } from "lucide-react";
import { useEffect, useState } from "react";

import { Eyebrow } from "@/components/eyebrow";
import {
	createUser,
	fetchSlackInstallations,
	fetchSlackWorkspaceMembers,
	fetchStaticSlackWorkspace,
	type CreateUserRequest,
	type SlackMember,
	type User,
	updateUser,
} from "@/lib/server";
import { cn } from "@/lib/utils";

/**
 * One row in the workspace dropdown — unified shape covering both
 * OAuth installations and the static-token (env-configured)
 * workspace. The dropdown doesn't care which kind it is; the only
 * UX difference is a small `(env)` suffix on the static one so the
 * operator knows it's running in single-workspace mode.
 */
interface WorkspaceOption {
	team_id: string;
	team_name: string | null;
	source: "oauth" | "env";
}

const inputClass =
	"w-full bg-white/5 border border-white/10 rounded-md px-2.5 py-1.5 text-xs placeholder:text-white/20 focus:outline-none focus:border-brand/40";

/**
 * Inline "add / edit user" form. Same component serves both modes —
 * `editing` is null for create, a User row for edit. Sends only the
 * fields that actually changed (PATCH semantics) on edit; fresh
 * POST on create.
 *
 * Validation parity with the server: the at-least-one-address rule
 * (email OR full slack pair) is shown inline so users don't have to
 * wait for a 422 round-trip. Server enforces it regardless.
 */
export function UserForm({
	editing,
	onCancel,
	onSaved,
	onError,
}: {
	editing: User | null;
	onCancel: () => void;
	onSaved: () => Promise<void>;
	onError: (msg: string) => void;
}) {
	// ── Form state ──
	const [displayName, setDisplayName] = useState(editing?.display_name ?? "");
	const [email, setEmail] = useState(editing?.email ?? "");
	const [slackTeamId, setSlackTeamId] = useState(editing?.slack_team_id ?? "");
	const [slackUserId, setSlackUserId] = useState(editing?.slack_user_id ?? "");
	const [role, setRole] = useState(editing?.role ?? "");
	const [accessLevel, setAccessLevel] = useState(editing?.access_level ?? "");
	const [pool, setPool] = useState(editing?.pool ?? "");
	const [isOperator, setIsOperator] = useState(editing?.is_operator ?? false);
	// New users default to active=true; existing users carry their current
	// state. Toggling this off is the canonical way to revoke login + stop
	// the router from picking the user without deleting their history.
	const [active, setActive] = useState(editing?.active ?? true);
	const [password, setPassword] = useState("");
	const [submitting, setSubmitting] = useState(false);

	// ── Slack workspace picker ──
	// Loaded lazily on mount. Combines OAuth installations
	// (`slack_installations` table) with the static-token workspace
	// (set via SLACK_BOT_TOKEN env). Without merging both, an
	// operator running in static-token mode would see "no workspaces
	// installed" here even though Settings → Slack shows the env
	// workspace just fine — confusing and wrong.
	const [workspaces, setWorkspaces] = useState<WorkspaceOption[]>([]);
	const [members, setMembers] = useState<SlackMember[] | null>(null);
	const [loadingMembers, setLoadingMembers] = useState(false);
	const [memberLoadError, setMemberLoadError] = useState<string | null>(null);

	useEffect(() => {
		// Fire both lookups in parallel; merge the results. Either
		// can fail independently (no OAuth configured / no env token)
		// so we tolerate either side returning empty / null.
		Promise.all([
			fetchSlackInstallations().catch(() => []),
			fetchStaticSlackWorkspace().catch(() => null),
		]).then(([installs, staticWs]) => {
			const merged: WorkspaceOption[] = installs.map((i) => ({
				team_id: i.team_id,
				team_name: i.team_name,
				source: "oauth",
			}));
			// Avoid duplicates if the same team_id ever appears in both
			// (shouldn't, but be defensive).
			if (
				staticWs &&
				!merged.some((w) => w.team_id === staticWs.team_id)
			) {
				merged.push({
					team_id: staticWs.team_id,
					team_name: staticWs.team_name,
					source: "env",
				});
			}
			setWorkspaces(merged);
		});
	}, []);

	// When the operator picks a team from the dropdown, fetch its
	// members so the user ID field becomes a combobox of real people
	// rather than a free-text paste box. Works for BOTH OAuth and
	// static-token workspaces — the server's get_client_for_team
	// falls back to the env client when no DB row matches the
	// team_id.
	useEffect(() => {
		if (!slackTeamId || !workspaces.some((w) => w.team_id === slackTeamId)) {
			setMembers(null);
			return;
		}
		setLoadingMembers(true);
		setMemberLoadError(null);
		fetchSlackWorkspaceMembers(slackTeamId)
			.then(setMembers)
			.catch((err: unknown) =>
				setMemberLoadError(
					err instanceof Error ? err.message : "Failed to load members",
				),
			)
			.finally(() => setLoadingMembers(false));
	}, [slackTeamId, workspaces]);

	const hasEmail = email.trim().length > 0;
	const hasSlackTeam = slackTeamId.trim().length > 0;
	const hasSlackUser = slackUserId.trim().length > 0;
	const hasFullSlack = hasSlackTeam && hasSlackUser;
	const hasPartialSlack = hasSlackTeam !== hasSlackUser;
	const addressOk = hasEmail || hasFullSlack;
	const addressError = hasPartialSlack
		? "Slack team ID and user ID must be set together."
		: !addressOk
			? "A user needs at least one delivery address (email or Slack)."
			: null;

	const handleSubmit = async (e: React.FormEvent) => {
		e.preventDefault();
		if (addressError) return;
		if (password && password.length < 8) {
			onError("Password must be at least 8 characters.");
			return;
		}

		setSubmitting(true);
		try {
			const body: CreateUserRequest = {
				display_name: displayName || null,
				email: email || null,
				slack_team_id: slackTeamId || null,
				slack_user_id: slackUserId || null,
				role: role || null,
				access_level: accessLevel || null,
				pool: pool || null,
				is_operator: isOperator,
				active,
				// Only send password if it's non-empty. Blank + edit
				// means "don't touch the password."
				...(password ? { password } : {}),
			};

			if (editing) {
				// PATCH — server treats null as "leave alone" for most
				// fields. `is_operator` is always sent because it's a
				// boolean, not an absence.
				await updateUser(editing.id, body);
			} else {
				await createUser(body);
			}
			await onSaved();
		} catch (err) {
			onError(err instanceof Error ? err.message : "Save failed");
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
					{editing ? "Edit user" : "New user"}
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
				<Field label="Display name">
					<input
						value={displayName}
						onChange={(e) => setDisplayName(e.target.value)}
						className={inputClass}
						placeholder="Alice Singh"
					/>
				</Field>

				<Field label="Email">
					<input
						type="email"
						value={email}
						onChange={(e) => setEmail(e.target.value)}
						className={inputClass}
						placeholder="alice@company.com"
					/>
				</Field>

				<Field
					label="Slack workspace"
					hint={
						workspaces.length === 0
							? "No Slack workspaces installed. Add one from Settings → Slack, or set SLACK_BOT_TOKEN for single-workspace mode."
							: "Pick a workspace the app is installed in, or paste a team ID manually."
					}
				>
					{workspaces.length > 0 ? (
						<select
							value={slackTeamId}
							onChange={(e) => {
								setSlackTeamId(e.target.value);
								// Clear the user ID when workspace changes — IDs
								// are team-scoped so the previous U… wouldn't resolve.
								setSlackUserId("");
							}}
							className={inputClass}
						>
							<option value="">—</option>
							{workspaces.map((w) => (
								<option key={w.team_id} value={w.team_id}>
									{w.team_name || w.team_id}
									{w.source === "env" ? " (env)" : ""}
								</option>
							))}
						</select>
					) : (
						<input
							value={slackTeamId}
							onChange={(e) => setSlackTeamId(e.target.value)}
							className={cn(inputClass, "font-mono")}
							placeholder="T01ABC234"
						/>
					)}
				</Field>

				<Field
					label="Slack member"
					hint={
						memberLoadError
							? memberLoadError
							: loadingMembers
								? "Loading members…"
								: members && members.length === 0
									? "No members found."
									: "Pick from the workspace, or paste a user ID."
					}
				>
					{members && members.length > 0 ? (
						<select
							value={slackUserId}
							onChange={(e) => setSlackUserId(e.target.value)}
							className={inputClass}
						>
							<option value="">—</option>
							{members.map((m) => (
								<option key={m.id} value={m.id}>
									{m.real_name
										? `${m.real_name} (@${m.name})`
										: `@${m.name}`}
								</option>
							))}
						</select>
					) : (
						<input
							value={slackUserId}
							onChange={(e) => setSlackUserId(e.target.value)}
							className={cn(inputClass, "font-mono")}
							placeholder="U01XYZ789"
							disabled={loadingMembers}
						/>
					)}
				</Field>

				<Field
					label="Role"
					hint="Free-form routing label. E.g. kyc-reviewer, support-tier-1."
				>
					<input
						value={role}
						onChange={(e) => setRole(e.target.value)}
						className={inputClass}
						placeholder="kyc-reviewer"
					/>
				</Field>

				<Field label="Access level">
					<input
						value={accessLevel}
						onChange={(e) => setAccessLevel(e.target.value)}
						className={inputClass}
						placeholder="senior"
					/>
				</Field>

				<Field label="Pool">
					<input
						value={pool}
						onChange={(e) => setPool(e.target.value)}
						className={inputClass}
						placeholder="ops"
					/>
				</Field>

				<Field
					label={editing ? "New password (leave blank to keep)" : "Password"}
					hint="Set for users who need to log into the dashboard. Min 8 chars."
				>
					<input
						type="password"
						value={password}
						onChange={(e) => setPassword(e.target.value)}
						className={inputClass}
						placeholder={editing?.has_password ? "••••••••" : ""}
					/>
				</Field>

				<div className="col-span-2 space-y-2 pt-1">
					<label
						htmlFor="is_active"
						className="flex items-center gap-2 text-xs text-white/70 cursor-pointer"
					>
						<input
							type="checkbox"
							id="is_active"
							checked={active}
							onChange={(e) => setActive(e.target.checked)}
							className="h-3.5 w-3.5 rounded border-white/20 bg-white/5"
						/>
						<span>
							Active — can log in and receive task assignments.
							{editing && !active && (
								<span className="text-yellow-400/80 ml-1">
									(currently inactive — login + routing blocked)
								</span>
							)}
						</span>
					</label>

					<label
						htmlFor="is_operator"
						className="flex items-center gap-2 text-xs text-white/70 cursor-pointer"
					>
						<input
							type="checkbox"
							id="is_operator"
							checked={isOperator}
							onChange={(e) => setIsOperator(e.target.checked)}
							className="h-3.5 w-3.5 rounded border-white/20 bg-white/5"
						/>
						<span>
							Operator — can manage users and see all tasks in the dashboard.
						</span>
					</label>
				</div>
			</div>

			{addressError && (
				<div className="mt-3 text-yellow-400/90 text-[11px] border border-yellow-400/30 bg-yellow-400/5 rounded-md px-3 py-2">
					{addressError}
				</div>
			)}

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
					disabled={submitting || !!addressError}
					className="px-4 py-1.5 bg-brand text-black font-semibold text-xs rounded-md hover:bg-brand/90 disabled:opacity-40 transition-colors"
				>
					{submitting
						? editing
							? "Saving…"
							: "Creating…"
						: editing
							? "Save changes"
							: "Create user"}
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
