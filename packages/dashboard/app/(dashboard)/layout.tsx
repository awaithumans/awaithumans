import { AuthGuard } from "@/components/auth-guard";
import { Sidebar } from "@/components/sidebar";

/**
 * Dashboard layout — sidebar + main content area. Wrapped in AuthGuard,
 * which redirects unauthenticated users to /login when the server has
 * DASHBOARD_PASSWORD set. When auth is off, AuthGuard is a pass-through.
 */
export default function DashboardLayout({
	children,
}: {
	children: React.ReactNode;
}) {
	return (
		<AuthGuard>
			<div className="flex min-h-screen">
				<Sidebar />
				<main className="flex-1 overflow-x-auto">
					<div className="max-w-7xl mx-auto px-8 py-8">{children}</div>
				</main>
			</div>
		</AuthGuard>
	);
}
