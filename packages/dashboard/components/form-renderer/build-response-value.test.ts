/**
 * Unit tests for `buildResponseValue` — the wire-shaping step the
 * dashboard runs before posting a completion to the server.
 *
 * Pins the rule that motivated the helper:
 *   - blank (null/undefined) optional fields are DROPPED from the JSON
 *   - required fields with null are KEPT (so server-side validation
 *     surfaces a clear error rather than the dashboard silently
 *     swallowing the violation)
 *   - empty strings stay as empty strings (user explicitly cleared
 *     the field; "" is a meaningful value distinct from "untouched")
 *   - empty arrays stay as empty arrays (multi_select with nothing
 *     picked is a valid value, not "untouched")
 *   - section_collapse children are flat at the same FormValue level
 *   - subform / table rows recurse so the same rule applies per row
 */

import { describe, expect, it } from "vitest";

import type { FormDefinition } from "@/lib/form-types";

import { buildResponseValue } from "./build-response-value";
import type { FormValue } from "./types";

function form(fields: FormDefinition["fields"]): FormDefinition {
	return { version: 1, fields };
}

// Compact field factories — the unit tests only care about
// `kind`, `name`, `required`, and (where relevant) nested `fields`.
// The runtime checks at the FormField level are the responsibility
// of the discriminated-union parser elsewhere.
function shortText(name: string, required: boolean) {
	return {
		kind: "short_text",
		name,
		label: name,
		required,
		hint: null,
		placeholder: null,
		max_length: null,
		min_length: null,
		default: null,
		subtype: "plain",
	} as unknown as FormDefinition["fields"][number];
}

function multiSelect(name: string, required: boolean) {
	return {
		kind: "multi_select",
		name,
		label: name,
		required,
		hint: null,
		options: [],
		default: null,
	} as unknown as FormDefinition["fields"][number];
}

function aSwitch(name: string, required: boolean) {
	return {
		kind: "switch",
		name,
		label: name,
		required,
		hint: null,
		true_label: "Yes",
		false_label: "No",
		default: null,
	} as unknown as FormDefinition["fields"][number];
}

describe("buildResponseValue", () => {
	it("drops null on a non-required field", () => {
		const f = form([shortText("reason", false), aSwitch("approved", true)]);
		const value: FormValue = { reason: null, approved: true };

		expect(buildResponseValue(f, value)).toEqual({ approved: true });
	});

	it("keeps null on a required field so server can flag it", () => {
		const f = form([aSwitch("approved", true), shortText("reason", true)]);
		const value: FormValue = { approved: null, reason: null };

		expect(buildResponseValue(f, value)).toEqual({
			approved: null,
			reason: null,
		});
	});

	it("preserves empty string distinctly from null", () => {
		// User typing and clearing produces "". That's a meaningful
		// value (the human said "the answer is empty") versus null
		// ("untouched"). Send it as-is.
		const f = form([shortText("reason", false)]);
		expect(buildResponseValue(f, { reason: "" })).toEqual({ reason: "" });
	});

	it("preserves empty arrays for multi_select", () => {
		// "Nothing selected" is a valid completion for an optional
		// multi_select; don't drop it.
		const f = form([multiSelect("tags", false)]);
		expect(buildResponseValue(f, { tags: [] })).toEqual({ tags: [] });
	});

	it("drops undefined the same as null", () => {
		const f = form([shortText("reason", false)]);
		expect(buildResponseValue(f, { reason: undefined })).toEqual({});
	});

	it("flattens section_collapse children at the same level", () => {
		const collapse = {
			kind: "section_collapse",
			name: "advanced",
			label: "advanced",
			required: false,
			hint: null,
			title: "Advanced",
			subtitle: null,
			default_open: false,
			fields: [shortText("tier", false), shortText("ref", true)],
		} as unknown as FormDefinition["fields"][number];
		const f = form([aSwitch("approved", true), collapse]);

		const value: FormValue = {
			approved: true,
			tier: null,
			ref: null,
		};

		// `tier` (optional) is dropped; `ref` (required) is kept.
		expect(buildResponseValue(f, value)).toEqual({
			approved: true,
			ref: null,
		});
	});

	it("recurses into subform rows", () => {
		const subform = {
			kind: "subform",
			name: "items",
			label: "items",
			required: true,
			hint: null,
			min_count: null,
			max_count: null,
			initial_count: 1,
			add_label: "Add",
			remove_label: "Remove",
			fields: [shortText("sku", true), shortText("note", false)],
		} as unknown as FormDefinition["fields"][number];
		const f = form([subform]);

		const value: FormValue = {
			items: [
				{ sku: "A-1", note: "ok" },
				{ sku: "A-2", note: null },
			],
		};

		expect(buildResponseValue(f, value)).toEqual({
			items: [
				{ sku: "A-1", note: "ok" },
				{ sku: "A-2" },
			],
		});
	});

	it("recurses into table rows by column", () => {
		const table = {
			kind: "table",
			name: "amounts",
			label: "amounts",
			required: false,
			hint: null,
			min_rows: null,
			max_rows: null,
			initial_rows: 1,
			allow_add_row: true,
			allow_remove_row: true,
			columns: [
				{
					name: "currency",
					label: "currency",
					kind: "short_text",
					required: true,
					placeholder: null,
					options: null,
					currency_code: null,
					min_value: null,
					max_value: null,
					default: null,
				},
				{
					name: "memo",
					label: "memo",
					kind: "short_text",
					required: false,
					placeholder: null,
					options: null,
					currency_code: null,
					min_value: null,
					max_value: null,
					default: null,
				},
			],
		} as unknown as FormDefinition["fields"][number];
		const f = form([table]);

		const value: FormValue = {
			amounts: [
				{ currency: "USD", memo: null },
				{ currency: "EUR", memo: "" },
			],
		};

		expect(buildResponseValue(f, value)).toEqual({
			amounts: [{ currency: "USD" }, { currency: "EUR", memo: "" }],
		});
	});
});
