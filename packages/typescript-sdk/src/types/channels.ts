/**
 * Server-side channel + task-handler interfaces (reference only).
 *
 * The TS SDK doesn't implement these — Slack and email channels live
 * server-side in Python. Exported so adapter authors and the docs site
 * can reference the same shape.
 *
 * Mirrors the channel-extension contracts defined in the master
 * architecture pillar (the four buckets: channel, verifier, router,
 * task-type handler).
 */

import type { JsonSchema7Type } from "zod-to-json-schema";

import type { HumanIdentity } from "./routing.js";

// ─── Channel ───────────────────────────────────────────────────────────

export interface Channel {
	/** Send the task notification + render the response UI in this channel. */
	notify(context: ChannelContext): Promise<ChannelNotifyResult>;

	/** Handle a response submitted through this channel. */
	handleResponse?(
		context: ChannelResponseContext,
	): Promise<ChannelHandleResult>;
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

// ─── Task-type handler ─────────────────────────────────────────────────

export interface TaskTypeHandler {
	/** Render the payload for display in a specific channel format. */
	renderPayload(
		payload: unknown,
		schema: JsonSchema7Type,
		format: RenderFormat,
	): unknown;

	/** Render the response form/UI in a specific channel format. */
	renderResponseForm(schema: JsonSchema7Type, format: RenderFormat): unknown;
}

export type RenderFormat = "dashboard" | "slack-block-kit" | "email-html";
