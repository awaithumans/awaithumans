/**
 * SDK types — re-exports from per-domain type files.
 *
 * Import from here, not from individual files:
 *
 *     import type { AwaitHumanOptions, TaskStatus, AssignTo } from "./types";
 *
 * Mirrors `awaithumans/types/__init__.py` so the cross-language docs
 * line up: each Python module here has a same-name TS counterpart.
 */

export type {
	AwaitHumanOptions,
	TaskRecord,
	TaskStatus,
} from "./task";
export { TERMINAL_STATUSES } from "./task";

export type {
	Assignment,
	AssignTo,
	HumanIdentity,
	RouteContext,
	Router,
} from "./routing";

export type {
	VerificationContext,
	Verifier,
	VerifierConfig,
	VerifierResult,
} from "./verification";

export type {
	Channel,
	ChannelContext,
	ChannelHandleResult,
	ChannelNotifyResult,
	ChannelResponseContext,
	RenderFormat,
	TaskTypeHandler,
} from "./channels";
