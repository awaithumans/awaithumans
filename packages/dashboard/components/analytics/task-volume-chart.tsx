/**
 * Grouped-bar chart for tasks created vs completed, per day.
 *
 * Hand-rolled SVG — sub-kilobyte, no chart library dep, legible enough
 * for a sparkline-density view. When the Analytics page grows beyond
 * "a few cards" we can swap in Recharts or Tremor, but for V1 this
 * keeps the bundle lean and the render deterministic.
 */

import type { TaskStatsByDay } from "@/lib/server";

const HEIGHT = 140;
const BAR_GAP = 1;       // px between the created/completed pair inside one day
const DAY_GAP = 2;       // px between day groups
const LABEL_ROW_HEIGHT = 14;

export function TaskVolumeChart({ data }: { data: TaskStatsByDay[] }) {
	const max = Math.max(1, ...data.flatMap((d) => [d.created, d.completed]));
	const days = data.length;

	// One "day group" = 2 bars + 1 inner gap.
	// Total width is flexible — we let CSS scale. We output a viewBox
	// so bars compress gracefully on narrow screens.
	const groupWidth = 12; // logical units per day group
	const barWidth = (groupWidth - BAR_GAP) / 2;
	const width = days * (groupWidth + DAY_GAP);

	return (
		<div className="w-full">
			<div className="flex items-center gap-4 mb-3 text-xs text-white/50">
				<Legend color="var(--color-brand)" label="Created" />
				<Legend color="rgba(255,255,255,0.45)" label="Completed" />
				<span className="ml-auto text-white/30">Last {days} days</span>
			</div>
			<svg
				viewBox={`0 0 ${width} ${HEIGHT + LABEL_ROW_HEIGHT}`}
				preserveAspectRatio="none"
				className="w-full h-[160px]"
				role="img"
				aria-label="Task volume per day"
			>
				{/* Zero baseline */}
				<line
					x1="0"
					y1={HEIGHT}
					x2={width}
					y2={HEIGHT}
					stroke="rgba(255,255,255,0.08)"
					strokeWidth="0.5"
				/>
				{data.map((d, i) => {
					const x = i * (groupWidth + DAY_GAP);
					const createdH = (d.created / max) * HEIGHT;
					const completedH = (d.completed / max) * HEIGHT;
					return (
						<g key={d.date}>
							<rect
								x={x}
								y={HEIGHT - createdH}
								width={barWidth}
								height={createdH}
								fill="var(--color-brand)"
								opacity="0.85"
							/>
							<rect
								x={x + barWidth + BAR_GAP}
								y={HEIGHT - completedH}
								width={barWidth}
								height={completedH}
								fill="rgba(255,255,255,0.45)"
							/>
						</g>
					);
				})}
				{/* First + last + midpoint day labels — keep the axis legible
				    on narrow screens without scribbling 30 stamps. */}
				{[0, Math.floor((days - 1) / 2), days - 1]
					.filter((v, idx, arr) => arr.indexOf(v) === idx)
					.map((i) => {
						const x = i * (groupWidth + DAY_GAP) + groupWidth / 2;
						return (
							<text
								key={i}
								x={x}
								y={HEIGHT + LABEL_ROW_HEIGHT - 2}
								textAnchor="middle"
								fontSize="6"
								fill="rgba(255,255,255,0.3)"
							>
								{formatShortDate(data[i].date)}
							</text>
						);
					})}
			</svg>
		</div>
	);
}

function Legend({ color, label }: { color: string; label: string }) {
	return (
		<span className="inline-flex items-center gap-1.5">
			<span
				className="inline-block w-2 h-2 rounded-sm"
				style={{ background: color }}
			/>
			{label}
		</span>
	);
}

function formatShortDate(iso: string): string {
	// "2026-04-17" → "Apr 17"
	const d = new Date(`${iso}T00:00:00Z`);
	return d.toLocaleDateString("en-US", {
		month: "short",
		day: "numeric",
		timeZone: "UTC",
	});
}
