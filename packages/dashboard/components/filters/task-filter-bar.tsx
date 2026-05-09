"use client";

import { Search, X } from "lucide-react";
import type { TaskStatus } from "@/lib/server";
import { cn } from "@/lib/utils";

/**
 * Shared filter UI for the tasks list and the audit log.
 *
 * Why a shared component: pre-#73 we copy-pasted ~80 lines of filter
 * markup between `/` (tasks) and `/audit` (terminal tasks), and the
 * two were already drifting in spacing + behaviour. Now both pages
 * lay out the same controls with the same affordances; only the
 * status-option list and a couple of toggles differ.
 *
 * Page-owned, URL-synced state stays in the page component — this
 * component is just the visual shell + the on-change plumbing.
 */

export interface FilterState {
	status: TaskStatus | "all";
	assignedTo: string;
	unassigned: boolean;
	mine: boolean;
}

export interface StatusOption {
	label: string;
	value: TaskStatus | "all";
}

export interface TaskFilterBarProps {
	filters: FilterState;
	onChange: (patch: Partial<FilterState>) => void;
	isOperator: boolean;
	statusOptions: readonly StatusOption[];
	/**
	 * Hide the "Unassigned only" toggle on contexts where it doesn't
	 * make sense (e.g. audit page — terminal tasks are past
	 * assignment, the toggle would always return zero).
	 */
	showUnassignedToggle?: boolean;
	searchPlaceholder?: string;
}

export function TaskFilterBar({
	filters,
	onChange,
	isOperator,
	statusOptions,
	showUnassignedToggle = true,
	searchPlaceholder = "search email, name, or Slack ID",
}: TaskFilterBarProps) {
	const filtersActive =
		filters.status !== "all" ||
		filters.assignedTo !== "" ||
		filters.unassigned ||
		filters.mine;

	const clearAll = () =>
		onChange({
			status: "all",
			assignedTo: "",
			unassigned: false,
			mine: false,
		});

	return (
		<div className="space-y-3 mb-6">
			{/* Top row — search + quick toggles + clear */}
			<div className="border border-white/10 rounded-lg p-3 flex flex-wrap items-center gap-2">
				{/* Search field with icon */}
				<div className="relative flex-1 min-w-[260px] max-w-md">
					<Search className="absolute left-2.5 top-1/2 -translate-y-1/2 w-4 h-4 text-white/30 pointer-events-none" />
					<input
						type="text"
						placeholder={searchPlaceholder}
						value={filters.assignedTo}
						disabled={filters.unassigned || filters.mine}
						onChange={(e) =>
							onChange({ assignedTo: e.target.value })
						}
						className={cn(
							"w-full bg-white/5 border border-white/10 rounded-md pl-8 pr-3 py-1.5 text-sm text-white",
							"placeholder:text-white/30 focus:outline-none focus:border-brand/40",
							"disabled:opacity-40 disabled:cursor-not-allowed",
						)}
					/>
				</div>

				{/* Quick toggle pills — visually grouped */}
				<div className="flex items-center gap-1 ml-auto">
					{showUnassignedToggle && (
						<TogglePill
							active={filters.unassigned}
							onClick={() =>
								onChange({
									unassigned: !filters.unassigned,
									// Mutually exclusive with Mine.
									mine: !filters.unassigned ? false : filters.mine,
								})
							}
							label="Unassigned"
						/>
					)}
					{isOperator && (
						<TogglePill
							active={filters.mine}
							onClick={() =>
								onChange({
									mine: !filters.mine,
									unassigned: !filters.mine ? false : filters.unassigned,
								})
							}
							label="Mine only"
						/>
					)}

					{/* Status select — last, since users hit it less often */}
					<label className="flex items-center gap-2 text-xs text-white/50 ml-2">
						<span>Status</span>
						<select
							value={filters.status}
							onChange={(e) =>
								onChange({
									status: e.target.value as TaskStatus | "all",
								})
							}
							className={cn(
								"bg-white/5 border border-white/10 rounded-md px-2 py-1 text-sm text-white",
								"focus:outline-none focus:border-brand/40",
							)}
						>
							{statusOptions.map((o) => (
								<option key={o.value} value={o.value}>
									{o.label}
								</option>
							))}
						</select>
					</label>

					{filtersActive && (
						<button
							type="button"
							onClick={clearAll}
							className="ml-1 text-xs text-white/40 hover:text-white/70 transition-colors px-2"
						>
							Clear
						</button>
					)}
				</div>
			</div>

			{/* Active filter chips — appear below the bar so the user can see
			    what's filtering at a glance and remove them one by one without
			    hunting through the controls. */}
			{filtersActive && (
				<div className="flex flex-wrap items-center gap-2 px-1">
					<span className="text-xs text-white/30 uppercase tracking-wider">
						Active:
					</span>
					{filters.status !== "all" && (
						<FilterChip
							label={`Status: ${labelForStatus(statusOptions, filters.status)}`}
							onRemove={() => onChange({ status: "all" })}
						/>
					)}
					{filters.assignedTo && (
						<FilterChip
							label={`Assignee: ${filters.assignedTo}`}
							onRemove={() => onChange({ assignedTo: "" })}
						/>
					)}
					{filters.unassigned && (
						<FilterChip
							label="Unassigned only"
							onRemove={() => onChange({ unassigned: false })}
						/>
					)}
					{filters.mine && (
						<FilterChip
							label="Mine only"
							onRemove={() => onChange({ mine: false })}
						/>
					)}
				</div>
			)}
		</div>
	);
}

function TogglePill({
	active,
	onClick,
	label,
}: {
	active: boolean;
	onClick: () => void;
	label: string;
}) {
	return (
		<button
			type="button"
			onClick={onClick}
			className={cn(
				"px-3 py-1 text-xs rounded-full border transition-colors",
				active
					? "bg-brand/15 text-brand border-brand/40"
					: "bg-white/5 text-white/60 border-white/10 hover:text-white/90 hover:border-white/20",
			)}
			aria-pressed={active}
		>
			{label}
		</button>
	);
}

function FilterChip({
	label,
	onRemove,
}: {
	label: string;
	onRemove: () => void;
}) {
	return (
		<span className="inline-flex items-center gap-1 px-2 py-0.5 text-xs rounded-md bg-brand/10 text-brand border border-brand/30">
			{label}
			<button
				type="button"
				onClick={onRemove}
				aria-label={`Remove filter ${label}`}
				className="hover:bg-brand/20 rounded-sm p-0.5 -mr-0.5 transition-colors"
			>
				<X className="w-3 h-3" />
			</button>
		</span>
	);
}

function labelForStatus(
	options: readonly StatusOption[],
	value: TaskStatus | "all",
): string {
	return options.find((o) => o.value === value)?.label ?? value;
}
