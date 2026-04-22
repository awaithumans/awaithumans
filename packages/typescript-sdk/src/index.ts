export { awaitHuman } from "./await-human";

// ─── SDK types (used by developers in their agent code) ─────────────
export type {
	AwaitHumanOptions,
	AssignTo,
	HumanIdentity,
	TaskStatus,
	TaskRecord,
	VerifierConfig,
	VerificationContext,
	VerifierResult,
} from "./types";

export { TERMINAL_STATUSES } from "./types";

// ─── Server-side interfaces (exported for reference / adapter authors only) ──
// These interfaces are implemented by the Python server, not the TS SDK.
// They are exported so adapter authors and documentation can reference them.
export type {
	Router,
	RouteContext,
	Assignment,
	Channel,
	ChannelContext,
	ChannelNotifyResult,
	ChannelResponseContext,
	ChannelHandleResult,
	TaskTypeHandler,
	RenderFormat,
} from "./types";

export { awaitHumanInputSchema } from "./schemas";

export {
	AwaitHumansError,
	MarketplaceNotAvailableError,
	PollError,
	SchemaValidationError,
	ServerUnreachableError,
	TaskAlreadyTerminalError,
	TaskCancelledError,
	TaskCreateError,
	TaskNotFoundError,
	TaskTimeoutError,
	TimeoutRangeError,
	VerificationExhaustedError,
} from "./errors";

export { awaitAgent, awaitAny } from "./reserved";
