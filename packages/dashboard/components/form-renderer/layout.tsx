import { useState, type ReactNode } from "react";
import type {
	DividerField,
	SectionCollapseField,
	SectionField,
} from "@/lib/form-types";

// ─── Section ─────────────────────────────────────────────────────────

export function SectionRenderer({ field }: { field: SectionField }) {
	return (
		<div className="pt-4 pb-1 border-t border-white/5 first:border-t-0 first:pt-0">
			<h3 className="text-sm font-semibold text-white">{field.title}</h3>
			{field.subtitle && (
				<p className="text-white/40 text-xs mt-0.5">{field.subtitle}</p>
			)}
		</div>
	);
}

// ─── Divider ─────────────────────────────────────────────────────────

export function DividerRenderer({ field: _ }: { field: DividerField }) {
	return <hr className="border-white/10" />;
}

// ─── SectionCollapse ─────────────────────────────────────────────────

export function SectionCollapseRenderer({
	field,
	children,
}: {
	field: SectionCollapseField;
	children: ReactNode;
}) {
	const [open, setOpen] = useState(field.default_open);
	return (
		<div className="border border-white/10 rounded-md overflow-hidden">
			<button
				type="button"
				onClick={() => setOpen((o) => !o)}
				className="w-full flex items-center justify-between px-4 py-3 text-left bg-white/5 hover:bg-white/10 transition-colors"
			>
				<div>
					<div className="text-sm font-semibold text-white">{field.title}</div>
					{field.subtitle && (
						<div className="text-white/40 text-xs mt-0.5">
							{field.subtitle}
						</div>
					)}
				</div>
				<span className="text-white/40 text-lg leading-none">
					{open ? "−" : "+"}
				</span>
			</button>
			{open && <div className="p-4 space-y-4">{children}</div>}
		</div>
	);
}
