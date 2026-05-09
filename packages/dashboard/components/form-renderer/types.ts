/**
 * Shared types for the form-renderer module. Kept in a `.ts` (not
 * `.tsx`) file so test files and other non-JSX consumers can import
 * them without dragging the renderer's React surface through Vite's
 * import analysis.
 */

export type FormValue = Record<string, unknown>;
