// Types for the embed-token mint helper. See spec §4.4.

export interface EmbedTokenOptions {
	taskId: string;
	parentOrigin: string;
	apiKey: string;
	sub?: string;
	ttlSeconds?: number;
	serverUrl?: string;
}

export interface EmbedTokenResult {
	embedToken: string;
	embedUrl: string;
	expiresAt: string;
}
