/**
 * Routing-shaped types — `assignTo` shapes the SDK accepts and the
 * router-side reference interfaces the Python server implements.
 *
 * Mirrors `awaithumans/types/routing.py`. The TS SDK doesn't run a
 * router itself; these interfaces are exported so adapter authors and
 * documentation can reference the same shape the server uses.
 */

import type { JsonSchema7Type } from "zod-to-json-schema";

// ─── AssignTo ──────────────────────────────────────────────────────────

export type AssignTo =
	| string // email — direct assignment
	| string[] // multiple emails — first to claim
	| { pool: string } // named pool
	| { role: string } // role-based
	| { role: string; accessLevel: string } // role + access level
	| { userId: string } // internal user ID
	| { marketplace: true }; // reserved for Phase 3

// Reserved for Phase 4 — do not implement yet
// | { capability: string; region?: string }
// | { agentEndpoint: string }
// | { preferAgent: boolean; fallbackHuman: boolean }

// ─── Server-side router interface (reference only) ─────────────────────

export interface Router {
	resolve(assignTo: AssignTo, context: RouteContext): Promise<Assignment>;
}

export interface RouteContext {
	task: string;
	payload: unknown;
	payloadSchema: JsonSchema7Type;
}

export interface Assignment {
	assignees: HumanIdentity[];
	mode: "first_claim" | "all";
}

export interface HumanIdentity {
	id: string;
	email: string;
	displayName?: string;
	roles?: string[];
	accessLevel?: string;
}
