import { cn } from "@/lib/utils";
import type {
	OpinionScaleField,
	RankingField,
	SliderField,
	StarRatingField,
} from "@/lib/form-types";
import { FieldWrapper } from "./field-wrapper";

// ─── Slider ──────────────────────────────────────────────────────────

export function SliderRenderer({
	field,
	value,
	onChange,
	disabled,
}: {
	field: SliderField;
	value: unknown;
	onChange: (v: unknown) => void;
	disabled?: boolean;
}) {
	const current =
		typeof value === "number"
			? value
			: typeof field.default === "number"
				? field.default
				: (field.min + field.max) / 2;
	return (
		<FieldWrapper field={field}>
			<div className="space-y-2">
				<div className="flex justify-between text-xs text-white/50">
					<span>{field.prefix}{field.min}{field.suffix}</span>
					<span className="text-brand">
						{field.prefix}
						{current}
						{field.suffix}
					</span>
					<span>{field.prefix}{field.max}{field.suffix}</span>
				</div>
				<input
					id={field.name}
					type="range"
					min={field.min}
					max={field.max}
					step={field.step}
					value={current}
					onChange={(e) => onChange(Number(e.target.value))}
					disabled={disabled}
					className="w-full accent-brand"
				/>
			</div>
		</FieldWrapper>
	);
}

// ─── StarRating ──────────────────────────────────────────────────────

export function StarRatingRenderer({
	field,
	value,
	onChange,
	disabled,
}: {
	field: StarRatingField;
	value: unknown;
	onChange: (v: unknown) => void;
	disabled?: boolean;
}) {
	const current = typeof value === "number" ? value : 0;
	return (
		<FieldWrapper field={field}>
			<div className="flex gap-1">
				{Array.from({ length: field.max }).map((_, i) => {
					const v = i + 1;
					const filled = v <= current;
					return (
						<button
							key={v}
							type="button"
							onClick={() => onChange(v)}
							disabled={disabled}
							aria-label={`${v} star${v === 1 ? "" : "s"}`}
							className={cn(
								"w-8 h-8 text-2xl leading-none transition-colors",
								filled ? "text-brand" : "text-white/20 hover:text-white/40",
							)}
						>
							★
						</button>
					);
				})}
			</div>
		</FieldWrapper>
	);
}

// ─── OpinionScale ────────────────────────────────────────────────────

export function OpinionScaleRenderer({
	field,
	value,
	onChange,
	disabled,
}: {
	field: OpinionScaleField;
	value: unknown;
	onChange: (v: unknown) => void;
	disabled?: boolean;
}) {
	const current = typeof value === "number" ? value : null;
	const values: number[] = [];
	for (let v = field.min; v <= field.max; v++) values.push(v);
	return (
		<FieldWrapper field={field}>
			<div className="space-y-2">
				<div className="flex gap-1 flex-wrap">
					{values.map((v) => (
						<button
							key={v}
							type="button"
							onClick={() => onChange(v)}
							disabled={disabled}
							className={cn(
								"min-w-[36px] h-9 text-sm rounded-md border transition-colors",
								current === v
									? "bg-brand/20 text-brand border-brand/40"
									: "bg-white/5 text-white/60 border-white/10 hover:text-white",
							)}
						>
							{v}
						</button>
					))}
				</div>
				{(field.min_label || field.max_label) && (
					<div className="flex justify-between text-xs text-white/40">
						<span>{field.min_label}</span>
						<span>{field.max_label}</span>
					</div>
				)}
			</div>
		</FieldWrapper>
	);
}

// ─── Ranking ─────────────────────────────────────────────────────────

/**
 * Baseline: reorderable list with ↑/↓ buttons per item. Drag-and-drop is a
 * later upgrade; the wire format (ordered list of option values) doesn't change.
 */
export function RankingRenderer({
	field,
	value,
	onChange,
	disabled,
}: {
	field: RankingField;
	value: unknown;
	onChange: (v: unknown) => void;
	disabled?: boolean;
}) {
	const initialOrder = field.options.map((o) => o.value);
	const current =
		Array.isArray(value) && value.every((v) => typeof v === "string")
			? (value as string[])
			: initialOrder;

	const move = (index: number, delta: number) => {
		const next = [...current];
		const target = index + delta;
		if (target < 0 || target >= next.length) return;
		[next[index], next[target]] = [next[target], next[index]];
		onChange(next);
	};

	const labelFor = (v: string) =>
		field.options.find((o) => o.value === v)?.label ?? v;

	return (
		<FieldWrapper field={field}>
			<ol className="space-y-1.5">
				{current.map((v, i) => (
					<li
						key={v}
						className="flex items-center gap-2 px-3 py-2 rounded-md border border-white/10 bg-white/5 text-sm"
					>
						<span className="text-white/40 w-5 font-mono text-xs">{i + 1}.</span>
						<span className="flex-1">{labelFor(v)}</span>
						<button
							type="button"
							onClick={() => move(i, -1)}
							disabled={disabled || i === 0}
							className="w-7 h-7 text-white/60 hover:text-white disabled:opacity-30"
							aria-label="Move up"
						>
							↑
						</button>
						<button
							type="button"
							onClick={() => move(i, 1)}
							disabled={disabled || i === current.length - 1}
							className="w-7 h-7 text-white/60 hover:text-white disabled:opacity-30"
							aria-label="Move down"
						>
							↓
						</button>
					</li>
				))}
			</ol>
		</FieldWrapper>
	);
}
