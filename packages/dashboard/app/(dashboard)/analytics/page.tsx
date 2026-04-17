"use client";

import {
	Activity,
	CheckCircle,
	Clock,
	ListChecks,
} from "lucide-react";
import { useEffect, useMemo, useState } from "react";

import { ChannelMix } from "@/components/analytics/channel-mix";
import { StatCard } from "@/components/analytics/stat-card";
import { TaskVolumeChart } from "@/components/analytics/task-volume-chart";
import { ErrorBanner } from "@/components/error-banner";
import { fetchTaskStats, type TaskStats } from "@/lib/server";

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
				<div className="text-white/30 text-sm">Loading stats…</div>
			) : stats ? (
				<div className="space-y-6">
					{/* KPI row */}
					<div className="grid grid-cols-4 gap-4">
						<StatCard
							icon={ListChecks}
							label="Tasks in flight"
							value={openTaskCount}
							sub={`${stats.totals.completed ?? 0} completed all-time`}
						/>
						<StatCard
							icon={CheckCircle}
							label="Completion rate"
							accent
							value={
								stats.completion_rate === null
									? "—"
									: `${(stats.completion_rate * 100).toFixed(0)}%`
							}
							sub={
								stats.completion_rate === null
									? "No terminal tasks yet"
									: "completed / terminal"
							}
						/>
						<StatCard
							icon={Clock}
							label="Avg time to complete"
							value={formatDuration(stats.avg_completion_seconds)}
							sub={
								stats.avg_completion_seconds === null
									? `in last ${windowDays} days`
									: `mean across ${windowDays} days`
							}
						/>
						<StatCard
							icon={Activity}
							label="Timed out"
							value={stats.totals.timed_out ?? 0}
							sub={`${stats.totals.cancelled ?? 0} cancelled`}
						/>
					</div>

					{/* Chart */}
					<section>
						<h2 className="text-sm font-semibold mb-3 text-white/70">
							Volume
						</h2>
						<div className="border border-white/10 rounded-lg p-5 bg-white/[0.015]">
							<TaskVolumeChart data={stats.by_day} />
						</div>
					</section>

					{/* Channels */}
					<section>
						<h2 className="text-sm font-semibold mb-3 text-white/70">
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
