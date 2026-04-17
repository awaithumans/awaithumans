/**
 * Grouped-bar chart for tasks created vs completed, per day.
 *
 * Hand-rolled SVG — sub-kilobyte, no chart library dep, legible enough
 * for a sparkline-density view. When the Analytics page grows beyond
 * "a few cards" we can swap in Recharts or Tremor, but for V1 this
 * keeps the bundle lean and the render deterministic.
 */

import type { TaskStatsByDay } from "@/lib/server";

const CHART_HEIGHT = 140;
const BAR_GAP = 1;
const DAY_GAP = 2;
const GROUP_WIDTH = 12;
const LABEL_ROW = 16;
// Horizontal padding so the first / last axis labels don't clip at the
// viewBox edges.
const SIDE_PAD = 18;

export function TaskVolumeChart({ data }: { data: TaskStatsByDay[] }) {
	const max = Math.max(1, ...data.flatMap((d) => [d.created, d.completed]));
	const days = data.length;

	const barWidth = (GROUP_WIDTH - BAR_GAP) / 2;
	const barsWidth = days * (GROUP_WIDTH + DAY_GAP);
	const width = barsWidth + SIDE_PAD * 2;
	const total = { created: 0, completed: 0 };
	for (const d of data) {
		total.created += d.created;
		total.completed += d.completed;
	}

	return (
		<div className="w-full">
			<div className="flex items-center gap-5 mb-4 text-xs">
				<Legend
					color="var(--color-brand)"
					label="Created"
					count={total.created}
				/>
				<Legend
					color="rgba(255,255,255,0.45)"
					label="Completed"
					count={total.completed}
				/>
				<span className="ml-auto text-white/35 text-[11px]">
					Last {days} days
				</span>
			</div>
			<svg
				viewBox={`0 0 ${width} ${CHART_HEIGHT + LABEL_ROW}`}
				preserveAspectRatio="none"
				className="w-full h-[160px]"
				role="img"
				aria-label="Task volume per day"
			>
				{/* Horizontal gridlines at 0/50/100% of max. */}
				{[0, 0.5, 1].map((frac) => {
					const y = CHART_HEIGHT - frac * CHART_HEIGHT;
					return (
						<line
							key={frac}
							x1={SIDE_PAD}
							y1={y}
							x2={width - SIDE_PAD}
							y2={y}
							stroke="rgba(255,255,255,0.05)"
							strokeWidth="0.5"
							strokeDasharray={frac === 0 ? undefined : "1,2"}
						/>
					);
				})}

				{data.map((d, i) => {
					const x = SIDE_PAD + i * (GROUP_WIDTH + DAY_GAP);
					const createdH = (d.created / max) * CHART_HEIGHT;
					const completedH = (d.completed / max) * CHART_HEIGHT;
					return (
						<g key={d.date}>
							<rect
								x={x}
								y={CHART_HEIGHT - createdH}
								width={barWidth}
								height={createdH}
								fill="var(--color-brand)"
								opacity="0.9"
								rx="0.5"
							>
								<title>{`${formatShortDate(d.date)}: ${d.created} created`}</title>
							</rect>
							<rect
								x={x + barWidth + BAR_GAP}
								y={CHART_HEIGHT - completedH}
								width={barWidth}
								height={completedH}
								fill="rgba(255,255,255,0.45)"
								rx="0.5"
							>
								<title>{`${formatShortDate(d.date)}: ${d.completed} completed`}</title>
							</rect>
						</g>
					);
				})}

				{/* First + midpoint + last date stamps only — more than that
				    turns into a blur at 30 days / 5 px per day. */}
				{[0, Math.floor((days - 1) / 2), days - 1]
					.filter((v, idx, arr) => arr.indexOf(v) === idx)
					.map((i) => {
						const x =
							SIDE_PAD + i * (GROUP_WIDTH + DAY_GAP) + GROUP_WIDTH / 2;
						return (
							<text
								key={i}
								x={x}
								y={CHART_HEIGHT + LABEL_ROW - 4}
								textAnchor="middle"
								fontSize="7"
								fontFamily="var(--font-geist-sans), sans-serif"
								fill="rgba(255,255,255,0.35)"
							>
								{formatShortDate(data[i].date)}
							</text>
						);
					})}
			</svg>
		</div>
	);
}

function Legend({
	color,
	label,
	count,
}: {
	color: string;
	label: string;
	count?: number;
}) {
	return (
		<span className="inline-flex items-center gap-1.5 text-white/55">
			<span
				className="inline-block w-2 h-2 rounded-sm"
				style={{ background: color }}
			/>
			{label}
			{count !== undefined && (
				<span className="text-white/35 tabular-nums">· {count}</span>
			)}
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
