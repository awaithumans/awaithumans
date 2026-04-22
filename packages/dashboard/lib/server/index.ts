/**
 * API client for the awaithumans server — per-domain modules.
 *
 * Pages import from "@/lib/server" and get the full surface.
 * Types are re-exported for convenience (canonical home is lib/types.ts).
 */

export type {
	AuditEntry,
	CompleteTaskRequest,
	HealthResponse,
	Task,
	TaskStatus,
} from "@/lib/types";

export { fetchAuditTrail } from "./audit";
export {
	createFirstOperator,
	fetchMe,
	fetchSetupStatus,
	login,
	logout,
	type MeResponse,
	type SetupStatusResponse,
} from "./auth";
export { apiFetch, UnauthorizedError } from "./client";
export {
	createEmailIdentity,
	deleteEmailIdentity,
	fetchEmailIdentities,
	type CreateEmailIdentityRequest,
	type EmailIdentity,
	type EmailTransport,
} from "./email-identities";
export { fetchHealth } from "./health";
export {
	fetchSlackInstallations,
	uninstallSlackWorkspace,
	type SlackInstallation,
} from "./slack";
export {
	fetchTaskStats,
	type TaskStats,
	type TaskStatsByDay,
} from "./stats";
export { fetchSystemStatus, type SystemStatus } from "./status";
export { cancelTask, completeTask, fetchTask, fetchTasks } from "./tasks";
export {
	clearUserPassword,
	createUser,
	deleteUser,
	fetchUsers,
	setUserPassword,
	updateUser,
	type CreateUserRequest,
	type UpdateUserRequest,
	type User,
	type UserListFilters,
} from "./users";
