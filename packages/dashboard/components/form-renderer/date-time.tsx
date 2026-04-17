import type {
	DatePickerField,
	DateRangeField,
	DateTimePickerField,
	TimePickerField,
} from "@/lib/form-types";
import { FieldWrapper } from "./field-wrapper";

const inputClass =
	"bg-white/5 border border-white/10 rounded-md px-3 py-2 text-sm text-white focus:outline-none focus:border-brand/40";

// ─── DatePicker ──────────────────────────────────────────────────────

export function DatePickerRenderer({
	field,
	value,
	onChange,
	disabled,
}: {
	field: DatePickerField;
	value: unknown;
	onChange: (v: unknown) => void;
	disabled?: boolean;
}) {
	const stringValue = typeof value === "string" ? value : "";
	return (
		<FieldWrapper field={field}>
			<input
				id={field.name}
				type="date"
				value={stringValue}
				onChange={(e) => onChange(e.target.value || null)}
				min={field.min_date ?? undefined}
				max={field.max_date ?? undefined}
				disabled={disabled}
				className={`${inputClass} w-full`}
			/>
		</FieldWrapper>
	);
}

// ─── DateTimePicker ──────────────────────────────────────────────────

export function DateTimePickerRenderer({
	field,
	value,
	onChange,
	disabled,
}: {
	field: DateTimePickerField;
	value: unknown;
	onChange: (v: unknown) => void;
	disabled?: boolean;
}) {
	// <input type="datetime-local"> uses "YYYY-MM-DDTHH:MM" — strip timezone.
	const stringValue = typeof value === "string" ? value.slice(0, 16) : "";
	return (
		<FieldWrapper field={field}>
			<input
				id={field.name}
				type="datetime-local"
				value={stringValue}
				onChange={(e) => onChange(e.target.value || null)}
				min={field.min_datetime ?? undefined}
				max={field.max_datetime ?? undefined}
				disabled={disabled}
				className={`${inputClass} w-full`}
			/>
			{field.timezone && (
				<p className="text-white/30 text-xs mt-1">Timezone: {field.timezone}</p>
			)}
		</FieldWrapper>
	);
}

// ─── DateRange ───────────────────────────────────────────────────────

type Range = { start: string | null; end: string | null };

export function DateRangeRenderer({
	field,
	value,
	onChange,
	disabled,
}: {
	field: DateRangeField;
	value: unknown;
	onChange: (v: unknown) => void;
	disabled?: boolean;
}) {
	const r: Range =
		value && typeof value === "object"
			? (value as Range)
			: { start: null, end: null };

	return (
		<FieldWrapper field={field}>
			<div className="flex items-center gap-2">
				<input
					type="date"
					value={r.start ?? ""}
					onChange={(e) =>
						onChange({ start: e.target.value || null, end: r.end })
					}
					min={field.min_date ?? undefined}
					max={field.max_date ?? undefined}
					disabled={disabled}
					className={`${inputClass} flex-1`}
					aria-label="Start date"
				/>
				<span className="text-white/40 text-sm">→</span>
				<input
					type="date"
					value={r.end ?? ""}
					onChange={(e) =>
						onChange({ start: r.start, end: e.target.value || null })
					}
					min={field.min_date ?? undefined}
					max={field.max_date ?? undefined}
					disabled={disabled}
					className={`${inputClass} flex-1`}
					aria-label="End date"
				/>
			</div>
		</FieldWrapper>
	);
}

// ─── TimePicker ──────────────────────────────────────────────────────

export function TimePickerRenderer({
	field,
	value,
	onChange,
	disabled,
}: {
	field: TimePickerField;
	value: unknown;
	onChange: (v: unknown) => void;
	disabled?: boolean;
}) {
	const stringValue = typeof value === "string" ? value : "";
	return (
		<FieldWrapper field={field}>
			<input
				id={field.name}
				type="time"
				value={stringValue}
				onChange={(e) => onChange(e.target.value || null)}
				min={field.min_time ?? undefined}
				max={field.max_time ?? undefined}
				step={field.step_minutes * 60}
				disabled={disabled}
				className={`${inputClass} w-full`}
			/>
		</FieldWrapper>
	);
}
