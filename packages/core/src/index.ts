export { awaitHuman } from "./await-human";

export type {
	AwaitHumanOptions,
	AssignTo,
	Router,
	RouteContext,
	Assignment,
	HumanIdentity,
	Verifier,
	VerificationContext,
	VerifierResult,
	Channel,
	ChannelContext,
	ChannelNotifyResult,
	ChannelResponseContext,
	ChannelHandleResult,
	TaskTypeHandler,
	RenderFormat,
	TaskStatus,
	TaskRecord,
} from "./types";

export { TERMINAL_STATUSES } from "./types";

export {
	AwaitHumansError,
	TimeoutError,
	SchemaValidationError,
	TimeoutRangeError,
	TaskAlreadyTerminalError,
	VerificationExhaustedError,
	MarketplaceNotAvailableError,
} from "./errors";

/** @reserved Phase 4 — agent-to-agent delegation. Not yet implemented. */
export function awaitAgent(): never {
	throw new Error(
		"awaitAgent is coming in Phase 4. Follow https://github.com/awaithumans/awaithumans for updates.",
	);
}

/** @reserved Phase 4 — universal delegation (human or agent). Not yet implemented. */
export function awaitAny(): never {
	throw new Error(
		"awaitAny is coming in Phase 4. Follow https://github.com/awaithumans/awaithumans for updates.",
	);
}
