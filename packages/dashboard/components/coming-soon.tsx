import type { LucideIcon } from "lucide-react";

export function ComingSoon({
	icon: Icon,
	title,
	body,
}: {
	icon: LucideIcon;
	title: string;
	body: string;
}) {
	return (
		<div className="max-w-2xl">
			<div className="flex items-center gap-3 mb-2">
				<div className="w-9 h-9 rounded-lg border border-white/10 flex items-center justify-center text-white/50">
					<Icon size={18} />
				</div>
				<h1 className="text-2xl font-bold">{title}</h1>
			</div>
			<p className="text-white/50 text-sm max-w-md mb-8">{body}</p>

			<div className="border border-dashed border-white/15 rounded-lg p-8 text-center">
				<div className="inline-flex items-center gap-2 px-2.5 py-1 rounded-full border border-brand/30 bg-brand/5 text-brand text-xs font-medium tracking-wide uppercase">
					<span className="w-1.5 h-1.5 rounded-full bg-brand" />
					Coming soon
				</div>
				<p className="text-white/30 text-sm mt-4">
					This page is on the launch roadmap. Tasks list, audit log, and
					channel integrations are functional today.
				</p>
			</div>
		</div>
	);
}
