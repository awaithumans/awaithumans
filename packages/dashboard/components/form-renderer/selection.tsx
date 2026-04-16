import { cn } from "@/lib/utils";
import type {
	MultiSelectField,
	PictureChoiceField,
	SingleSelectField,
	SwitchField,
} from "@/lib/form-types";
import { FieldWrapper } from "./field-wrapper";

// ─── Switch ──────────────────────────────────────────────────────────

export function SwitchRenderer({
	field,
	value,
	onChange,
	disabled,
}: {
	field: SwitchField;
	value: unknown;
	onChange: (v: unknown) => void;
	disabled?: boolean;
}) {
	const current = value as boolean | null | undefined;
	return (
		<FieldWrapper field={field}>
			<div className="flex gap-3">
				<button
					type="button"
					onClick={() => onChange(true)}
					disabled={disabled}
					className={cn(
						"px-4 py-2 text-sm rounded-md border transition-colors",
						current === true
							? "bg-[#00E676]/20 text-[#00E676] border-[#00E676]/40"
							: "bg-white/5 text-white/50 border-white/10 hover:text-white",
					)}
				>
					{field.true_label}
				</button>
				<button
					type="button"
					onClick={() => onChange(false)}
					disabled={disabled}
					className={cn(
						"px-4 py-2 text-sm rounded-md border transition-colors",
						current === false
							? "bg-red-400/20 text-red-400 border-red-400/40"
							: "bg-white/5 text-white/50 border-white/10 hover:text-white",
					)}
				>
					{field.false_label}
				</button>
			</div>
		</FieldWrapper>
	);
}

// ─── SingleSelect ────────────────────────────────────────────────────

export function SingleSelectRenderer({
	field,
	value,
	onChange,
	disabled,
}: {
	field: SingleSelectField;
	value: unknown;
	onChange: (v: unknown) => void;
	disabled?: boolean;
}) {
	const current = value as string | null | undefined;
	// Under ~4 options → radio buttons. More → dropdown.
	if (field.options.length <= 4) {
		return (
			<FieldWrapper field={field}>
				<div className="flex flex-wrap gap-2">
					{field.options.map((opt) => (
						<button
							key={opt.value}
							type="button"
							onClick={() => onChange(opt.value)}
							disabled={disabled}
							title={opt.hint ?? undefined}
							className={cn(
								"px-3 py-2 text-sm rounded-md border transition-colors",
								current === opt.value
									? "bg-[#00E676]/20 text-[#00E676] border-[#00E676]/40"
									: "bg-white/5 text-white/60 border-white/10 hover:text-white",
							)}
						>
							{opt.label}
						</button>
					))}
				</div>
			</FieldWrapper>
		);
	}

	return (
		<FieldWrapper field={field}>
			<select
				id={field.name}
				value={current ?? ""}
				onChange={(e) => onChange(e.target.value || null)}
				disabled={disabled}
				className="w-full bg-white/5 border border-white/10 rounded-md px-3 py-2 text-sm text-white focus:outline-none focus:border-[#00E676]/40"
			>
				<option value="">Select…</option>
				{field.options.map((opt) => (
					<option key={opt.value} value={opt.value}>
						{opt.label}
					</option>
				))}
			</select>
		</FieldWrapper>
	);
}

// ─── MultiSelect ─────────────────────────────────────────────────────

export function MultiSelectRenderer({
	field,
	value,
	onChange,
	disabled,
}: {
	field: MultiSelectField;
	value: unknown;
	onChange: (v: unknown) => void;
	disabled?: boolean;
}) {
	const current = Array.isArray(value) ? (value as string[]) : [];
	const toggle = (v: string) => {
		const next = current.includes(v)
			? current.filter((x) => x !== v)
			: [...current, v];
		onChange(next);
	};
	return (
		<FieldWrapper field={field}>
			<div className="flex flex-col gap-2">
				{field.options.map((opt) => {
					const checked = current.includes(opt.value);
					return (
						<label
							key={opt.value}
							className={cn(
								"flex items-start gap-2 px-3 py-2 rounded-md border text-sm cursor-pointer transition-colors",
								checked
									? "bg-[#00E676]/10 text-white border-[#00E676]/30"
									: "bg-white/5 text-white/70 border-white/10 hover:text-white",
							)}
						>
							<input
								type="checkbox"
								checked={checked}
								onChange={() => toggle(opt.value)}
								disabled={disabled}
								className="mt-1 accent-[#00E676]"
							/>
							<div>
								<div>{opt.label}</div>
								{opt.hint && (
									<div className="text-white/40 text-xs mt-0.5">{opt.hint}</div>
								)}
							</div>
						</label>
					);
				})}
			</div>
		</FieldWrapper>
	);
}

// ─── PictureChoice ───────────────────────────────────────────────────

export function PictureChoiceRenderer({
	field,
	value,
	onChange,
	disabled,
}: {
	field: PictureChoiceField;
	value: unknown;
	onChange: (v: unknown) => void;
	disabled?: boolean;
}) {
	const current = Array.isArray(value) ? (value as string[]) : [];

	const toggle = (v: string) => {
		if (field.multiple) {
			const next = current.includes(v)
				? current.filter((x) => x !== v)
				: [...current, v];
			onChange(next);
		} else {
			onChange(current.includes(v) ? [] : [v]);
		}
	};

	return (
		<FieldWrapper field={field}>
			<div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
				{field.options.map((opt) => {
					const selected = current.includes(opt.value);
					return (
						<button
							key={opt.value}
							type="button"
							onClick={() => toggle(opt.value)}
							disabled={disabled}
							className={cn(
								"rounded-md border overflow-hidden text-left transition-colors",
								selected
									? "border-[#00E676]/60 ring-2 ring-[#00E676]/30"
									: "border-white/10 hover:border-white/30",
							)}
						>
							{/* eslint-disable-next-line @next/next/no-img-element */}
							<img
								src={opt.image_url}
								alt={opt.label}
								className="w-full aspect-square object-cover"
							/>
							<div className="px-2 py-1.5 bg-black/40">
								<div className="text-sm text-white">{opt.label}</div>
								{opt.hint && (
									<div className="text-white/40 text-xs">{opt.hint}</div>
								)}
							</div>
						</button>
					);
				})}
			</div>
		</FieldWrapper>
	);
}
