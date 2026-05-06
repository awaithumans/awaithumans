/**
 * Build a `FormDefinition` from a Zod schema.
 *
 * The Python SDK has `extract_form()` driven by Pydantic; the server
 * uses `form_definition` to decide things like whether the email
 * channel emits Approve/Reject magic-link buttons or just a "Review
 * in dashboard" link-out (single Switch primitive → buttons; anything
 * else → link-out).
 *
 * Without this synthesis, every TS-created task got the link-out
 * fallback, even for the simple `z.object({ approved: z.boolean() })`
 * case where the magic-link path is the obvious DX win.
 *
 * Coverage today: boolean (Switch), string (ShortText / LongText),
 * number (ShortText), enum (SingleSelect). Enough for the email
 * magic-link path, which only fires for a single Switch or a small
 * SingleSelect anyway. The other 23 server primitives require
 * explicit `Annotated` decoration on Pydantic — Zod has no equivalent
 * affordance, so the long tail is intentionally left to a future
 * explicit-DSL escape hatch.
 *
 * Returns `null` when the schema isn't a `ZodObject`. Caller should
 * treat null as "no form_definition" and let the server / dashboard
 * fall back to JSON-schema rendering.
 */

import type { ZodType, ZodTypeAny } from "zod";

import type { FormDefinition, FormField } from "./definition.js";

// ─── Zod introspection helpers ─────────────────────────────────────────

interface ZodDef {
	typeName?: string;
	values?: unknown[];
	innerType?: ZodTypeAny;
	checks?: Array<{ kind?: string }>;
	defaultValue?: () => unknown;
}

function zdef(schema: ZodTypeAny): ZodDef {
	return (schema as unknown as { _def: ZodDef })._def;
}

/**
 * Strip ZodOptional / ZodNullable / ZodDefault layers and report
 * whether any of them made the field non-required.
 */
function unwrap(
	schema: ZodTypeAny,
): { inner: ZodTypeAny; required: boolean } {
	let current = schema;
	let required = true;
	// Bound the loop in case of pathological nesting.
	for (let i = 0; i < 8; i++) {
		const def = zdef(current);
		if (
			def.typeName === "ZodOptional" ||
			def.typeName === "ZodNullable" ||
			def.typeName === "ZodDefault"
		) {
			required = false;
			if (!def.innerType) break;
			current = def.innerType;
			continue;
		}
		break;
	}
	return { inner: current, required };
}

/**
 * Snake_case attribute → "Title Case" — same fallback as the Python
 * `_humanize` helper so labels look identical across SDKs.
 */
function humanize(name: string): string {
	return name
		.replace(/[_-]+/g, " ")
		.trim()
		.replace(/\w\S*/g, (w) => w[0].toUpperCase() + w.slice(1).toLowerCase());
}

function description(schema: ZodTypeAny): string | undefined {
	return (schema as unknown as { description?: string }).description;
}

// ─── Per-type field synthesis ──────────────────────────────────────────

function fieldFor(
	name: string,
	schema: ZodTypeAny,
	required: boolean,
): FormField | null {
	const def = zdef(schema);
	const label = description(schema) ?? humanize(name);
	const base = { name, label, required } as const;

	switch (def.typeName) {
		case "ZodBoolean":
			return { ...base, kind: "switch", true_label: "Yes", false_label: "No" };

		case "ZodString": {
			// Long text heuristic: explicit `.min(N)` >= 100. Conservative —
			// defaults to short_text. Operators who want the long-text
			// textarea can pass `z.string().min(200)` or wait for the
			// eventual explicit DSL.
			const hasLongMin = (def.checks ?? []).some(
				(c) => c.kind === "min" && (c as { value?: number }).value! >= 100,
			);
			return { ...base, kind: hasLongMin ? "long_text" : "short_text" };
		}

		case "ZodNumber":
			// The server's ShortText accepts a `number` input mode for
			// numeric fields; we keep things simple and emit a short_text
			// — the email-magic-link decision (single-Switch only)
			// doesn't care about numeric fields anyway.
			return { ...base, kind: "short_text" };

		case "ZodEnum": {
			const values = (def.values as string[] | undefined) ?? [];
			const options = values.map((v) => ({ value: v, label: v }));
			return { ...base, kind: "single_select", options };
		}

		default:
			// Unknown primitive — skip rather than emit a malformed field.
			// The server falls back to JSON-schema rendering, so the
			// dashboard still works; the email channel just won't get
			// magic-link treatment for unsupported types.
			return null;
	}
}

// ─── Public API ────────────────────────────────────────────────────────

export function extractForm(
	schema: ZodType<unknown>,
): FormDefinition | null {
	const def = zdef(schema as ZodTypeAny);
	if (def.typeName !== "ZodObject") return null;

	const shape = (
		schema as unknown as { shape: Record<string, ZodTypeAny> }
	).shape;
	if (!shape || typeof shape !== "object") return null;

	const fields: FormField[] = [];
	for (const [name, subSchema] of Object.entries(shape)) {
		const { inner, required } = unwrap(subSchema);
		const field = fieldFor(name, inner, required);
		if (field !== null) fields.push(field);
	}

	if (fields.length === 0) return null;
	return { fields };
}
