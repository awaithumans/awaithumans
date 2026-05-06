/**
 * Verifier types — config the SDK passes to the server and reference
 * shapes the server's verifier implementations consume / return.
 *
 * Mirrors `awaithumans/types/verification.py`. Verification runs
 * server-side; the SDK just hands across the config blob.
 */

import type { JsonSchema7Type } from "zod-to-json-schema";

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
 * Server-side verifier interface. Exported for reference / adapter
 * authors. The Python server implements this, not the TS SDK.
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
