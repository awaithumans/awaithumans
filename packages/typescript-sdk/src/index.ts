export { awaitHuman } from "./await-human.js";

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
} from "./types/index.js";

export { TERMINAL_STATUSES } from "./types/index.js";

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
} from "./types/index.js";

export { awaitHumanInputSchema } from "./schemas.js";

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
} from "./errors.js";

export { awaitAgent, awaitAny } from "./reserved.js";
