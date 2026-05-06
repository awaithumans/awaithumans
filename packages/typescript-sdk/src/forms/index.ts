/**
 * Forms — Zod → server-side FormDefinition synthesis.
 *
 * Mirrors `awaithumans/forms/__init__.py`. Public symbols re-exported
 * here so `import { extractForm } from "../forms"` resolves without
 * the consumer having to know which file owns which export.
 */

export type { FormDefinition, FormField } from "./definition";
export { extractForm } from "./extract";
