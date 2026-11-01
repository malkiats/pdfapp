/**
 * Catalog types. They are derived from the generated OpenAPI types
 * (src/lib/api/schema.d.ts, regenerated with `npm run api:types`), so the
 * frontend never hand-writes the shape of a contract object.
 */
import type { components } from "@/lib/api/schema";

type Schemas = components["schemas"];

export type Tool = Schemas["Tool"];
export type ToolCategory = Schemas["ToolCategory"];
export type ToolStatus = Schemas["ToolStatus"];
export type InputKind = Schemas["InputKind"];
export type ToolFaqItem = Schemas["ToolFaqItem"];

// Phase 2+ types (not yet in openapi.yaml)
export type Tier = "free" | "personal" | "pro";
export interface TierLimits {
  maxFilesPerJob: number;
  maxFileMb: number;
  maxPagesPerJob: number;
  maxProcessingSeconds: number;
}

/** Shape of shared/tool-catalog.json (see shared/tool-catalog.schema.json). */
export interface ToolCatalog {
  schema_version: 1;
  tools: Tool[];
}

/** Slim, serialisable projection sent to client components (search, menus). */
export interface ToolSummary {
  slug: string;
  title: string;
  description: string;
  category: string;
  categoryName: string;
  keywords: string[];
  status: ToolStatus;
}
