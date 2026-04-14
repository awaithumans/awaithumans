import type { ZodType } from "zod";
import type { JsonSchema7Type } from "zod-to-json-schema";

// ─── Core Primitive ─────────────────────────────────────────────────────

export interface AwaitHumanOptions<TPayload, TResponse> {
	/** Human-readable description of the task. */
	task: string;

	/** Zod schema for the payload — drives the UI the human sees. */
	payloadSchema: ZodType<TPayload>;

	/** The data sent to the human. Must conform to payloadSchema. */
	payload: TPayload;

	/** Zod schema for the response — drives the response form. */
	responseSchema: ZodType<TResponse>;

	/**
	 * Timeout in milliseconds. REQUIRED — no default.
	 * Min: 60,000 (1 minute). Max: 2,592,000,000 (30 days).
	 */
	timeoutMs: number;

	/** Who should handle this task. Optional — defaults to the server's default pool. */
	assignTo?: AssignTo;

	/** Notification channels. E.g., ["slack:#ops", "email:sara@co.com"]. */
	notify?: string[];

	/** AI verifier config — sent to the server for execution. Optional — no verifier = human answer trusted. */
	verifier?: VerifierConfig;

	/** Explicit idempotency key. Defaults to content hash (direct mode) or engine identity (durable adapters). */
	idempotencyKey?: string;

	/** If true, audit log hides the payload body. */
	redactPayload?: boolean;

	/** Server URL override. Defaults to AWAITHUMANS_URL env var or http://localhost:3001. */
	serverUrl?: string;
}

// ─── Routing ────────────────────────────────────────────────────────────

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

// ─── Router Interface ───────────────────────────────────────────────────

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

// ─── Verifier ───────────────────────────────────────────────────────────

/**
 * Verifier configuration — sent to the server, which executes it.
 * The SDK does NOT run verification locally. This is a config blob.
 */
export interface VerifierConfig {
	provider: string;
	model?: string;
	instructions: string;
	maxAttempts: number;
	apiKeyEnv?: string;
}

/**
 * Server-side verifier interface. Exported for reference / adapter authors.
 * The Python server implements this, not the TS SDK.
 */
export interface Verifier {
	verify(context: VerificationContext): Promise<VerifierResult>;
	maxAttempts: number;
}

export interface VerificationContext {
	task: string;
	payload: unknown;
	payloadSchema: JsonSchema7Type;
	/** Structured response from the human. Null if NL input. */
	response: unknown | null;
	responseSchema: JsonSchema7Type;
	/** Natural language text from Slack thread / email reply. */
	rawInput?: string;
	/** Which verification attempt (1, 2, 3...). */
	attempt: number;
	/** Reasons from prior failed verification attempts. */
	previousRejections: string[];
}

export interface VerifierResult {
	passed: boolean;
	/** Human-readable — shown to the human if rejected. */
	reason: string;
	/** Extracted from NL input, conforming to responseSchema. Only present when parsing NL. */
	parsedResponse?: unknown;
}

// ─── Channel Interface ──────────────────────────────────────────────────

export interface Channel {
	/** Send the task notification + render the response UI in this channel. */
	notify(context: ChannelContext): Promise<ChannelNotifyResult>;

	/** Handle a response submitted through this channel. */
	handleResponse?(context: ChannelResponseContext): Promise<ChannelHandleResult>;
}

export interface ChannelContext {
	taskId: string;
	task: string;
	payload: unknown;
	payloadSchema: JsonSchema7Type;
	responseSchema: JsonSchema7Type;
	assignees: HumanIdentity[];
}

export interface ChannelNotifyResult {
	success: boolean;
	channelMessageId?: string;
}

export interface ChannelResponseContext {
	taskId: string;
	rawInput?: string;
	structuredResponse?: unknown;
	respondedBy: HumanIdentity;
	channel: string;
}

export interface ChannelHandleResult {
	accepted: boolean;
	response?: unknown;
}

// ─── Task-Type Handler Interface ────────────────────────────────────────

export interface TaskTypeHandler {
	/** Render the payload for display in a specific channel format. */
	renderPayload(payload: unknown, schema: JsonSchema7Type, format: RenderFormat): unknown;

	/** Render the response form/UI in a specific channel format. */
	renderResponseForm(schema: JsonSchema7Type, format: RenderFormat): unknown;
}

export type RenderFormat = "dashboard" | "slack-block-kit" | "email-html";

// ─── Task State Machine ─────────────────────────────────────────────────

export type TaskStatus =
	| "created"
	| "notified"
	| "assigned"
	| "in_progress"
	| "submitted"
	| "verified"
	| "completed"
	| "rejected"
	| "timed_out"
	| "cancelled"
	| "verification_exhausted";

export const TERMINAL_STATUSES: readonly TaskStatus[] = [
	"completed",
	"timed_out",
	"cancelled",
	"verification_exhausted",
] as const;

// ─── Task Record ────────────────────────────────────────────────────────

export interface TaskRecord {
	id: string;
	idempotencyKey: string;
	task: string;
	payload: unknown;
	payloadSchema: JsonSchema7Type;
	responseSchema: JsonSchema7Type;
	status: TaskStatus;
	assignTo?: AssignTo;
	response?: unknown;
	verifierResult?: VerifierResult;
	createdAt: Date;
	updatedAt: Date;
	completedAt?: Date;
	timedOutAt?: Date;
	timeoutMs: number;
	redactPayload: boolean;
}

// ─── Reserved Phase 4 Stubs ─────────────────────────────────────────────

/** @reserved Phase 4 — agent-to-agent delegation. */
export type AwaitAgentOptions = never; // Stub — will be defined in Phase 4

/** @reserved Phase 4 — universal delegation (human or agent). */
export type AwaitAnyOptions = never; // Stub — will be defined in Phase 4
