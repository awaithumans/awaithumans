/**
 * FormField + FormDefinition wire types.
 *
 * Mirrors `awaithumans/forms/base.py` + `awaithumans/forms/definition.py`
 * on the Python side, but only carries the subset of fields the TS
 * synthesizer can actually emit. The full primitive union lives
 * server-side; this file only types what the TS SDK produces.
 *
 * The `kind` discriminator matches the server's Pydantic field
 * union, so a synthesized FormDefinition validates against
 * `FormDefinition.model_validate(...)` without any translation step.
 */

/**
 * Subset of the FormField wire shape that this synthesizer can emit.
 * Other primitives (DatePicker, Slider, Subform, etc.) live server-
 * side and the TS SDK can't synthesize them yet — Zod has no
 * `Annotated`-like affordance for the explicit-DSL path. The server
 * falls back to JSON-schema rendering for those.
 */
export interface FormField {
	kind: "switch" | "short_text" | "long_text" | "single_select";
	name: string;
	label?: string;
	hint?: string;
	required: boolean;
	// kind-specific extras (true_label/false_label for switch,
	// `options` for single_select, etc.) are widened to `unknown` so
	// this file doesn't have to mirror the full server-side primitive
	// schema on every change.
	[extra: string]: unknown;
}

export interface FormDefinition {
	fields: FormField[];
}
