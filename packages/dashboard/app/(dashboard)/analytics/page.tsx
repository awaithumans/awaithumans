"use client";

import {
	Activity,
	Clock,
	ListChecks,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";
import { useEffect, useMemo, useState } from "react";

import { ChannelMix } from "@/components/analytics/channel-mix";
import { TaskVolumeChart } from "@/components/analytics/task-volume-chart";
import { ErrorBanner } from "@/components/error-banner";
import { TerminalSpinner } from "@/components/terminal-spinner";
import { fetchTaskStats, type TaskStats } from "@/lib/server";
import { cn } from "@/lib/utils";

const WINDOW_OPTIONS = [7, 30, 90] as const;
type Window = (typeof WINDOW_OPTIONS)[number];

export default function AnalyticsPage() {
	const [windowDays, setWindowDays] = useState<Window>(30);
	const [stats, setStats] = useState<TaskStats | null>(null);
	const [error, setError] = useState<string | null>(null);

	useEffect(() => {
		setError(null);
		fetchTaskStats(windowDays)
			.then(setStats)
			.catch((err) =>
				setError(err instanceof Error ? err.message : "Failed to load"),
			);
	}, [windowDays]);

	const openTaskCount = useMemo(() => {
		if (!stats) return 0;
		return (
			(stats.totals.created ?? 0) +
			(stats.totals.assigned ?? 0) +
			(stats.totals.in_progress ?? 0) +
			(stats.totals.notified ?? 0) +
			(stats.totals.submitted ?? 0)
		);
	}, [stats]);

	return (
		<div className="max-w-5xl">
			<div className="flex items-start justify-between mb-8 gap-4">
				<div>
					<h1 className="text-2xl font-bold">Analytics</h1>
					<p className="text-white/45 text-sm mt-1">
						How your humans + agents are moving tasks through the system.
					</p>
				</div>
				<WindowPicker value={windowDays} onChange={setWindowDays} />
			</div>

			{error && <ErrorBanner message={error} />}

			{!stats && !error ? (
				<TerminalSpinner label="aggregating stats" size="md" />
			) : stats ? (
				<div className="space-y-10 analytics-reveal">
					{/* Hero metric: completion rate dominates; three supporting
					    stats stack to the right. Editorial hierarchy instead
					    of four identical cards. */}
					<div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
						<HeroMetric
							label="Completion rate"
							value={
								stats.completion_rate === null
									? "—"
									: `${(stats.completion_rate * 100).toFixed(0)}%`
							}
							note={
								stats.completion_rate === null
									? "No terminal tasks yet. A task becomes terminal when it's completed, timed out, cancelled, or exhausts its verifier."
									: "Of tasks that reached a terminal state, this share was completed by a human — the rest timed out or were cancelled."
							}
							className="lg:col-span-2 reveal-1"
						/>
						<div className="space-y-3 lg:col-span-1">
							<SupportingStat
								icon={ListChecks}
								label="In flight"
								value={openTaskCount}
								sub={`${stats.totals.completed ?? 0} completed all-time`}
								className="reveal-2"
							/>
							<SupportingStat
								icon={Clock}
								label="Avg time to complete"
								value={formatDuration(stats.avg_completion_seconds)}
								sub={
									stats.avg_completion_seconds === null
										? `in last ${windowDays} days`
										: `mean across ${windowDays} days`
								}
								className="reveal-3"
							/>
							<SupportingStat
								icon={Activity}
								label="Timed out"
								value={stats.totals.timed_out ?? 0}
								sub={`${stats.totals.cancelled ?? 0} cancelled`}
								className="reveal-4"
							/>
						</div>
					</div>

					{/* Chart */}
					<section className="reveal-5">
						<h2 className="text-xs font-semibold mb-3 text-muted uppercase tracking-[0.18em]">
							Volume
						</h2>
						<div className="border border-white/10 rounded-lg p-5 bg-white/[0.015]">
							<TaskVolumeChart data={stats.by_day} />
						</div>
					</section>

					{/* Channels */}
					<section className="reveal-6">
						<h2 className="text-xs font-semibold mb-3 text-muted uppercase tracking-[0.18em]">
							Completion channels
						</h2>
						<ChannelMix byChannel={stats.by_channel} />
					</section>
				</div>
			) : null}
		</div>
	);
}

function WindowPicker({
	value,
	onChange,
}: {
	value: Window;
	onChange: (v: Window) => void;
}) {
	return (
		<div className="inline-flex border border-white/10 rounded-md overflow-hidden">
			{WINDOW_OPTIONS.map((w) => (
				<button
					key={w}
					type="button"
					onClick={() => onChange(w)}
					className={
						value === w
							? "px-3 py-1.5 text-xs bg-brand/10 text-brand border-r border-white/10 last:border-r-0"
							: "px-3 py-1.5 text-xs text-white/50 hover:text-white transition-colors border-r border-white/10 last:border-r-0"
					}
				>
					{w}d
				</button>
			))}
		</div>
	);
}

function HeroMetric({
	label,
	value,
	note,
	className,
}: {
	label: string;
	value: React.ReactNode;
	note: string;
	className?: string;
}) {
	return (
		<div
			className={cn(
				"border border-white/10 rounded-lg bg-white/[0.015] p-8 flex flex-col justify-between min-h-[240px]",
				className,
			)}
		>
			<div>
				<div className="text-[10px] uppercase tracking-[0.22em] text-muted font-medium">
					{label}
				</div>
				<div className="mt-5 text-7xl font-bold text-brand tabular-nums leading-none">
					{value}
				</div>
			</div>
			<p className="text-muted text-xs mt-8 max-w-md leading-relaxed">
				{note}
			</p>
		</div>
	);
}

function SupportingStat({
	icon: Icon,
	label,
	value,
	sub,
	className,
}: {
	icon: LucideIcon;
	label: string;
	value: React.ReactNode;
	sub?: React.ReactNode;
	className?: string;
}) {
	return (
		<div
			className={cn(
				"border border-white/10 rounded-lg bg-white/[0.015] px-5 py-4",
				className,
			)}
		>
			<div className="flex items-center gap-2 text-muted text-[10px] uppercase tracking-wider font-medium">
				<Icon size={12} />
				<span>{label}</span>
			</div>
			<div className="mt-1.5 text-2xl font-semibold tabular-nums">{value}</div>
			{sub && <div className="mt-1 text-muted text-xs tabular-nums">{sub}</div>}
		</div>
	);
}

function formatDuration(seconds: number | null): string {
	if (seconds === null) return "—";
	if (seconds < 60) return `${Math.round(seconds)}s`;
	const minutes = seconds / 60;
	if (minutes < 60) return `${minutes.toFixed(1)}m`;
	const hours = minutes / 60;
	if (hours < 24) return `${hours.toFixed(1)}h`;
	const days = hours / 24;
	return `${days.toFixed(1)}d`;
}
