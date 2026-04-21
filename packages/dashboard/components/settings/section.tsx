import type { LucideIcon } from "lucide-react";

import { cn } from "@/lib/utils";

export function SettingsSection({
	icon: Icon,
	title,
	description,
	action,
	children,
	className,
	/**
	 * `flat` drops the outer card chrome so the section body flows
	 * directly under the header. Use for config readouts (System
	 * status) where each row is already a clear unit and a second
	 * card layer adds nothing but visual noise. Keep cards for
	 * sections with their own empty/error/form states (Slack,
	 * Email) — there, the chrome separates the section's internal
	 * world from the page.
	 */
	flat,
}: {
	icon: LucideIcon;
	title: string;
	description?: string;
	action?: React.ReactNode;
	children: React.ReactNode;
	className?: string;
	flat?: boolean;
}) {
	return (
		<section className={cn("space-y-3", className)}>
			<div className="flex items-start justify-between gap-4">
				<div className="flex items-start gap-3">
					<div className="w-8 h-8 rounded-md border border-white/10 flex items-center justify-center text-muted shrink-0 mt-0.5">
						<Icon size={16} />
					</div>
					<div>
						<h2 className="text-sm font-semibold">{title}</h2>
						{description && (
							<p className="text-muted text-xs mt-0.5 max-w-xl">
								{description}
							</p>
						)}
					</div>
				</div>
				{action && <div className="shrink-0">{action}</div>}
			</div>
			{flat ? (
				children
			) : (
				<div className="border border-white/10 rounded-lg bg-white/[0.015]">
					{children}
				</div>
			)}
		</section>
	);
}

export function StatusDot({
	state,
}: {
	state: "ok" | "warn" | "off";
}) {
	const color =
		state === "ok"
			? "bg-brand shadow-[0_0_8px_rgba(0,230,118,0.4)]"
			: state === "warn"
				? "bg-yellow-400"
				: "bg-white/20";
	return <span className={cn("inline-block w-1.5 h-1.5 rounded-full", color)} />;
}
