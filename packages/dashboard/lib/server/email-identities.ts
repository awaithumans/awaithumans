/**
 * Email sender identities — list / create / delete.
 *
 * Admin-gated by AWAITHUMANS_ADMIN_API_TOKEN on the server. The
 * dashboard only sees the public fields (`transport_config` is never
 * echoed back after create — operators rotate by upserting, not
 * reading back, to keep credentials out of the API surface).
 */

import { apiFetch } from "./client";

export type EmailTransport = "resend" | "smtp" | "logging" | "noop";

export interface EmailIdentity {
	id: string;
	display_name: string;
	from_email: string;
	from_name: string | null;
	reply_to: string | null;
	transport: EmailTransport | string;
	verified: boolean;
	verified_at: string | null;
}

export interface CreateEmailIdentityRequest {
	id: string;
	display_name: string;
	from_email: string;
	from_name?: string;
	reply_to?: string;
	transport: EmailTransport;
	transport_config: Record<string, unknown>;
}

export async function fetchEmailIdentities(): Promise<EmailIdentity[]> {
	return apiFetch<EmailIdentity[]>("/api/channels/email/identities");
}

export async function createEmailIdentity(
	body: CreateEmailIdentityRequest,
): Promise<EmailIdentity> {
	return apiFetch<EmailIdentity>("/api/channels/email/identities", {
		method: "POST",
		body: JSON.stringify(body),
	});
}

export async function deleteEmailIdentity(id: string): Promise<void> {
	await apiFetch<void>(
		`/api/channels/email/identities/${encodeURIComponent(id)}`,
		{ method: "DELETE" },
	);
}
