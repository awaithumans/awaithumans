import type {
	DisplayTextField,
	LongTextField,
	RichTextField,
	ShortTextField,
} from "@/lib/form-types";
import { FieldWrapper } from "./field-wrapper";

const inputClass =
	"w-full bg-white/5 border border-white/10 rounded-md px-3 py-2 text-sm text-white placeholder:text-white/20 focus:outline-none focus:border-brand/40";

// ─── DisplayText ─────────────────────────────────────────────────────

export function DisplayTextRenderer({ field }: { field: DisplayTextField }) {
	const paragraphs = field.text.split(/\n\n+/);
	return (
		<div className="space-y-2">
			{field.label && (
				<div className="text-xs font-semibold text-white/50 uppercase tracking-wider">
					{field.label}
				</div>
			)}
			{paragraphs.map((para, i) => (
				<p
					key={i}
					className="text-sm text-white/70 leading-relaxed whitespace-pre-wrap"
				>
					{para}
				</p>
			))}
		</div>
	);
}

// ─── ShortText ───────────────────────────────────────────────────────

const subtypeInputType: Record<ShortTextField["subtype"], string> = {
	plain: "text",
	email: "email",
	url: "url",
	phone: "tel",
	currency: "number",
	number: "number",
	password: "password",
};

export function ShortTextRenderer({
	field,
	value,
	onChange,
	disabled,
}: {
	field: ShortTextField;
	value: unknown;
	onChange: (v: unknown) => void;
	disabled?: boolean;
}) {
	const stringValue =
		value === null || value === undefined ? "" : String(value);

	const coerce = (raw: string): unknown => {
		if (raw === "") return null;
		if (field.subtype === "number" || field.subtype === "currency") {
			const n = Number(raw);
			return Number.isFinite(n) ? n : null;
		}
		return raw;
	};

	return (
		<FieldWrapper field={field}>
			<div className="relative">
				{field.subtype === "currency" && field.currency_code && (
					<span className="absolute left-3 top-1/2 -translate-y-1/2 text-white/40 text-sm pointer-events-none">
						{field.currency_code}
					</span>
				)}
				<input
					id={field.name}
					type={subtypeInputType[field.subtype]}
					value={stringValue}
					onChange={(e) => onChange(coerce(e.target.value))}
					placeholder={field.placeholder ?? undefined}
					minLength={field.min_length ?? undefined}
					maxLength={field.max_length ?? undefined}
					pattern={field.pattern ?? undefined}
					disabled={disabled}
					className={
						field.subtype === "currency" && field.currency_code
							? `${inputClass} pl-12`
							: inputClass
					}
					autoComplete={field.subtype === "password" ? "new-password" : "off"}
				/>
			</div>
		</FieldWrapper>
	);
}

// ─── LongText ────────────────────────────────────────────────────────

export function LongTextRenderer({
	field,
	value,
	onChange,
	disabled,
}: {
	field: LongTextField;
	value: unknown;
	onChange: (v: unknown) => void;
	disabled?: boolean;
}) {
	const stringValue =
		value === null || value === undefined ? "" : String(value);
	return (
		<FieldWrapper field={field}>
			<textarea
				id={field.name}
				value={stringValue}
				onChange={(e) => onChange(e.target.value || null)}
				placeholder={field.placeholder ?? undefined}
				rows={field.rows ?? 4}
				minLength={field.min_length ?? undefined}
				maxLength={field.max_length ?? undefined}
				disabled={disabled}
				className={`${inputClass} resize-y`}
			/>
		</FieldWrapper>
	);
}

// ─── RichText ────────────────────────────────────────────────────────

/**
 * Baseline: plain textarea that stores HTML-unescaped plain text. A richer
 * editor (Tiptap/Lexical) will replace this later. The wire format is a
 * string — upgrading the editor later does not break the contract.
 */
export function RichTextRenderer({
	field,
	value,
	onChange,
	disabled,
}: {
	field: RichTextField;
	value: unknown;
	onChange: (v: unknown) => void;
	disabled?: boolean;
}) {
	const stringValue =
		value === null || value === undefined ? "" : String(value);
	return (
		<FieldWrapper field={field}>
			<textarea
				id={field.name}
				value={stringValue}
				onChange={(e) => onChange(e.target.value || null)}
				placeholder={field.placeholder ?? undefined}
				rows={6}
				maxLength={field.max_length ?? undefined}
				disabled={disabled}
				className={`${inputClass} font-sans leading-relaxed resize-y`}
			/>
		</FieldWrapper>
	);
}
