/**
 * Downstream activity: stand-in for "actually move the money."
 *
 * Lives outside the workflow sandbox so it can do real I/O — call
 * a payments provider, write to a DB, hit a third-party API. The
 * workflow file (where determinism matters) imports just the type
 * signature.
 */

import { randomUUID } from "node:crypto";

export interface ProcessRefundInput {
	customerId: string;
	amountUsd: number;
	decisionNotes: string | null;
}

export async function processRefund(
	input: ProcessRefundInput,
): Promise<string> {
	console.log(
		`[activity] processing refund customer=${input.customerId} ` +
			`amount=$${input.amountUsd} notes=${input.decisionNotes ?? "(none)"}`,
	);
	// Real implementation would charge / refund here. For the demo,
	// pretend we got an ID back from the payments API.
	return `refund-${randomUUID()}`;
}
