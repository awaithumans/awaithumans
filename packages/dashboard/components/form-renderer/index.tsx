/**
 * FormRenderer — walks a FormDefinition and renders it with the dashboard's
 * per-primitive components. Layout primitives (section, divider,
 * section_collapse) have no value. Input primitives read and write into
 * `value` keyed by `field.name`.
 *
 * Recursive primitives (subform, section_collapse) recurse by re-entering
 * the dispatcher with their own child fields.
 */

"use client";

import type { FormDefinition, FormField } from "@/lib/form-types";
import {
	DisplayTextRenderer,
	LongTextRenderer,
	RichTextRenderer,
	ShortTextRenderer,
} from "./text";
import {
	MultiSelectRenderer,
	PictureChoiceRenderer,
	SingleSelectRenderer,
	SwitchRenderer,
} from "./selection";
import {
	OpinionScaleRenderer,
	RankingRenderer,
	SliderRenderer,
	StarRatingRenderer,
} from "./numeric";
import {
	DatePickerRenderer,
	DateRangeRenderer,
	DateTimePickerRenderer,
	TimePickerRenderer,
} from "./date-time";
import {
	FileUploadRenderer,
	HtmlBlockRenderer,
	ImageDisplayRenderer,
	PdfViewerRenderer,
	SignatureRenderer,
	VideoDisplayRenderer,
} from "./media";
import {
	DividerRenderer,
	SectionCollapseRenderer,
	SectionRenderer,
} from "./layout";
import { SubformRenderer, TableRenderer } from "./complex";

export type FormValue = Record<string, unknown>;

type Props = {
	form: FormDefinition;
	value: FormValue;
	onChange: (next: FormValue) => void;
	disabled?: boolean;
};

export function FormRenderer({ form, value, onChange, disabled }: Props) {
	return (
		<div className="space-y-4">
			{form.fields.map((field, i) => (
				<FieldDispatch
					key={`${field.name || field.kind}-${i}`}
					field={field}
					value={value}
					onChange={onChange}
					disabled={disabled}
				/>
			))}
		</div>
	);
}

function FieldDispatch({
	field,
	value,
	onChange,
	disabled,
}: {
	field: FormField;
	value: FormValue;
	onChange: (next: FormValue) => void;
	disabled?: boolean;
}) {
	const setField = (next: unknown) =>
		onChange({ ...value, [field.name]: next });

	switch (field.kind) {
		// ── Display (no value) ──────────────────────────────
		case "display_text":
			return <DisplayTextRenderer field={field} />;
		case "image":
			return <ImageDisplayRenderer field={field} />;
		case "video":
			return <VideoDisplayRenderer field={field} />;
		case "pdf_viewer":
			return <PdfViewerRenderer field={field} />;
		case "html":
			return <HtmlBlockRenderer field={field} />;

		// ── Layout ──────────────────────────────────────────
		case "section":
			return <SectionRenderer field={field} />;
		case "divider":
			return <DividerRenderer field={field} />;
		case "section_collapse":
			return (
				<SectionCollapseRenderer field={field}>
					{field.fields.map((child, j) => (
						<FieldDispatch
							key={`${child.name || child.kind}-${j}`}
							field={child}
							value={value}
							onChange={onChange}
							disabled={disabled}
						/>
					))}
				</SectionCollapseRenderer>
			);

		// ── Text input ──────────────────────────────────────
		case "short_text":
			return (
				<ShortTextRenderer
					field={field}
					value={value[field.name]}
					onChange={setField}
					disabled={disabled}
				/>
			);
		case "long_text":
			return (
				<LongTextRenderer
					field={field}
					value={value[field.name]}
					onChange={setField}
					disabled={disabled}
				/>
			);
		case "rich_text":
			return (
				<RichTextRenderer
					field={field}
					value={value[field.name]}
					onChange={setField}
					disabled={disabled}
				/>
			);

		// ── Selection ───────────────────────────────────────
		case "switch":
			return (
				<SwitchRenderer
					field={field}
					value={value[field.name]}
					onChange={setField}
					disabled={disabled}
				/>
			);
		case "single_select":
			return (
				<SingleSelectRenderer
					field={field}
					value={value[field.name]}
					onChange={setField}
					disabled={disabled}
				/>
			);
		case "multi_select":
			return (
				<MultiSelectRenderer
					field={field}
					value={value[field.name]}
					onChange={setField}
					disabled={disabled}
				/>
			);
		case "picture_choice":
			return (
				<PictureChoiceRenderer
					field={field}
					value={value[field.name]}
					onChange={setField}
					disabled={disabled}
				/>
			);

		// ── Numeric ─────────────────────────────────────────
		case "slider":
			return (
				<SliderRenderer
					field={field}
					value={value[field.name]}
					onChange={setField}
					disabled={disabled}
				/>
			);
		case "star_rating":
			return (
				<StarRatingRenderer
					field={field}
					value={value[field.name]}
					onChange={setField}
					disabled={disabled}
				/>
			);
		case "opinion_scale":
			return (
				<OpinionScaleRenderer
					field={field}
					value={value[field.name]}
					onChange={setField}
					disabled={disabled}
				/>
			);
		case "ranking":
			return (
				<RankingRenderer
					field={field}
					value={value[field.name]}
					onChange={setField}
					disabled={disabled}
				/>
			);

		// ── Date / time ─────────────────────────────────────
		case "date":
			return (
				<DatePickerRenderer
					field={field}
					value={value[field.name]}
					onChange={setField}
					disabled={disabled}
				/>
			);
		case "datetime":
			return (
				<DateTimePickerRenderer
					field={field}
					value={value[field.name]}
					onChange={setField}
					disabled={disabled}
				/>
			);
		case "date_range":
			return (
				<DateRangeRenderer
					field={field}
					value={value[field.name]}
					onChange={setField}
					disabled={disabled}
				/>
			);
		case "time":
			return (
				<TimePickerRenderer
					field={field}
					value={value[field.name]}
					onChange={setField}
					disabled={disabled}
				/>
			);

		// ── Media input ─────────────────────────────────────
		case "file_upload":
			return (
				<FileUploadRenderer
					field={field}
					value={value[field.name]}
					onChange={setField}
					disabled={disabled}
				/>
			);
		case "signature":
			return (
				<SignatureRenderer
					field={field}
					value={value[field.name]}
					onChange={setField}
					disabled={disabled}
				/>
			);

		// ── Complex ─────────────────────────────────────────
		case "table":
			return (
				<TableRenderer
					field={field}
					value={value[field.name]}
					onChange={setField}
					disabled={disabled}
				/>
			);
		case "subform":
			return (
				<SubformRenderer
					field={field}
					value={value[field.name]}
					onChange={setField}
					disabled={disabled}
					renderChildren={(entryValue, setEntry) => (
						<div className="space-y-3">
							{field.fields.map((child, j) => (
								<FieldDispatch
									key={`${child.name || child.kind}-${j}`}
									field={child}
									value={entryValue}
									onChange={setEntry}
									disabled={disabled}
								/>
							))}
						</div>
					)}
				/>
			);
	}
}

// ─── Initial value helper ────────────────────────────────────────────

/**
 * Build an initial form value (empty dict) from a FormDefinition. Picks up
 * per-field defaults where the primitive declares one.
 */
export function initialValueFor(form: FormDefinition): FormValue {
	const out: FormValue = {};
	walk(form.fields, out);
	return out;
}

function walk(fields: FormField[], out: FormValue): void {
	for (const f of fields) {
		if (!f.name) continue;
		switch (f.kind) {
			case "switch":
				out[f.name] = f.default ?? null;
				break;
			case "single_select":
				out[f.name] = f.default ?? null;
				break;
			case "multi_select":
				out[f.name] = f.default ?? [];
				break;
			case "picture_choice":
				out[f.name] = f.default ?? [];
				break;
			case "slider":
				out[f.name] = f.default ?? (f.min + f.max) / 2;
				break;
			case "star_rating":
				out[f.name] = f.default ?? 0;
				break;
			case "opinion_scale":
				out[f.name] = f.default ?? null;
				break;
			case "date":
			case "datetime":
			case "time":
				out[f.name] = f.default ?? null;
				break;
			case "ranking":
				out[f.name] = f.options.map((o) => o.value);
				break;
			case "table":
				out[f.name] = [];
				break;
			case "subform":
				out[f.name] = [];
				break;
			case "section_collapse":
				walk(f.fields, out);
				break;
			default:
				out[f.name] = null;
		}
	}
}
