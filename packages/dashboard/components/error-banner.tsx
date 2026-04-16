"use client";

export function ErrorBanner({ message }: { message: string }) {
	return (
		<div className="bg-red-500/10 border border-red-500/20 rounded-lg p-4 mb-4 text-red-400 text-sm">
			{message}
		</div>
	);
}
