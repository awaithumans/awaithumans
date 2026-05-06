/**
 * Unit tests for `extractForm` — the Zod → FormDefinition synthesizer.
 *
 * The server uses `form_definition` to decide channel-specific rendering.
 * The most important contract is the magic-link path in the email
 * channel: a SINGLE Switch primitive triggers Approve/Reject buttons;
 * anything else falls back to a link-out. These tests pin the shapes
 * that need to round-trip through to the server's renderer.
 */

import { describe, expect, it } from "vitest";
import { z } from "zod";

import { extractForm } from "../src/forms";

describe("extractForm", () => {
	it("emits a Switch for a single boolean field", () => {
		// This is the exact shape the email magic-link path needs.
		const schema = z.object({
			approved: z.boolean().describe("Approve this transfer?"),
		});

		const def = extractForm(schema);
		expect(def).not.toBeNull();
		expect(def!.fields).toHaveLength(1);
		expect(def!.fields[0]).toMatchObject({
			kind: "switch",
			name: "approved",
			label: "Approve this transfer?",
			required: true,
			true_label: "Yes",
			false_label: "No",
		});
	});

	it("falls back to humanized name when no description set", () => {
		const schema = z.object({ has_paid: z.boolean() });
		const def = extractForm(schema)!;
		expect(def.fields[0].label).toBe("Has Paid");
	});

	it("marks optional fields as not required", () => {
		const schema = z.object({
			approved: z.boolean(),
			reason: z.string().optional(),
		});
		const def = extractForm(schema)!;
		const reason = def.fields.find((f) => f.name === "reason")!;
		expect(reason.required).toBe(false);
	});

	it("nullable + default also flip required to false", () => {
		const schema = z.object({
			a: z.boolean().nullable(),
			b: z.boolean().default(true),
		});
		const def = extractForm(schema)!;
		expect(def.fields.find((f) => f.name === "a")!.required).toBe(false);
		expect(def.fields.find((f) => f.name === "b")!.required).toBe(false);
	});

	it("emits short_text for plain strings", () => {
		const schema = z.object({ note: z.string() });
		expect(extractForm(schema)!.fields[0].kind).toBe("short_text");
	});

	it("emits long_text when min length suggests a paragraph", () => {
		// `.min(N)` with N >= 100 is the heuristic for "the operator
		// expects a long answer." Anything shorter stays short_text.
		const schema = z.object({ essay: z.string().min(120) });
		expect(extractForm(schema)!.fields[0].kind).toBe("long_text");
	});

	it("emits single_select for ZodEnum", () => {
		const schema = z.object({
			priority: z.enum(["low", "medium", "high"]),
		});
		const field = extractForm(schema)!.fields[0];
		expect(field.kind).toBe("single_select");
		expect(field.options).toEqual([
			{ value: "low", label: "low" },
			{ value: "medium", label: "medium" },
			{ value: "high", label: "high" },
		]);
	});

	it("emits short_text for numbers", () => {
		// Numbers don't drive the magic-link decision, so a string-shape
		// short_text with the value parsed by the server is fine.
		const schema = z.object({ amount: z.number() });
		expect(extractForm(schema)!.fields[0].kind).toBe("short_text");
	});

	it("returns null for non-object schemas", () => {
		// FormDefinition only models record-shaped responses. A bare
		// boolean / string at the top level has no field name — there's
		// nothing to synthesize.
		expect(extractForm(z.boolean())).toBeNull();
		expect(extractForm(z.string())).toBeNull();
		expect(extractForm(z.array(z.string()))).toBeNull();
	});

	it("returns null when the object is empty", () => {
		expect(extractForm(z.object({}))).toBeNull();
	});

	it("skips fields whose primitive isn't supported yet", () => {
		// `z.date()` isn't in the synthesizer's coverage — it should be
		// dropped silently rather than emit a malformed field. The
		// server falls back to JSON-schema rendering for the omitted
		// field; the supported one still gets a synthesized Switch.
		const schema = z.object({
			when: z.date(),
			approved: z.boolean(),
		});
		const def = extractForm(schema)!;
		expect(def.fields).toHaveLength(1);
		expect(def.fields[0].name).toBe("approved");
	});

	it("preserves field order from the Zod object", () => {
		// The email magic-link decision is order-sensitive — Approve
		// first, Reject second. Pin order so future refactors don't
		// silently swap them.
		const schema = z.object({
			a: z.boolean(),
			b: z.string(),
			c: z.enum(["x", "y"]),
		});
		const names = extractForm(schema)!.fields.map((f) => f.name);
		expect(names).toEqual(["a", "b", "c"]);
	});
});
