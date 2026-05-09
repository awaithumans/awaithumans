/*
 * Headless layout — no nav, no sidebar, no footer. The embed renders
 * inside a partner's iframe and must be visually independent of the
 * regular dashboard chrome. The root <html> still carries `dark` so
 * design tokens resolve, and globals.css runs through the parent
 * layout so fonts and tokens apply.
 *
 * No <ConsoleBanner /> here — that warning is for operators using the
 * standalone dashboard, not for end-users embedded inside a partner
 * product. Showing it inside the iframe would leak our voice into the
 * partner's UX.
 */

export default function EmbedLayout({
	children,
}: {
	children: React.ReactNode;
}) {
	return <div className="min-h-screen bg-bg text-fg">{children}</div>;
}
