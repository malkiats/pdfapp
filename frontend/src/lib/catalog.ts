/**
 * Build-time loader for shared/tool-catalog.json (owned by the backend builder,
 * read-only here). The JSON is bundled at build time through the `@shared/*`
 * path alias, so every tool page is statically generated from the same file the
 * API serves. The full JSON Schema validation runs in tests
 * (tests/unit/catalog.test.ts); this module re-checks the invariants the UI
 * depends on and fails the build loudly if they break.
 */
import rawCatalog from "@shared/tool-catalog.json";
import type { Tool, ToolCatalog } from "@/types/catalog";

const SLUG_RE = /^[a-z0-9]+(-[a-z0-9]+)*$/;
const KNOWN_STATUSES = new Set(["available", "coming_soon"]);
const KNOWN_INPUT_KINDS = new Set(["file", "url", "text"]);

export class CatalogError extends Error {
  constructor(message: string) {
    super(`tool-catalog.json: ${message}`);
    this.name = "CatalogError";
  }
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function isStringArray(value: unknown): value is string[] {
  return Array.isArray(value) && value.every((v) => typeof v === "string");
}

/**
 * Structural checks the UI relies on. Returns the catalog typed against the
 * contract, or throws CatalogError. Unknown categories are allowed (the
 * contract says clients must render them gracefully).
 */
export function parseCatalog(input: unknown): ToolCatalog {
  if (!isRecord(input)) throw new CatalogError("root must be an object");
  if (input.schema_version !== 1) throw new CatalogError("unsupported schema_version");
  const tools = input.tools;
  if (!Array.isArray(tools) || tools.length === 0) throw new CatalogError("tools must be a non-empty array");

  const seen = new Set<string>();
  tools.forEach((tool, index) => {
    const where = `tools[${index}]`;
    if (!isRecord(tool)) throw new CatalogError(`${where} must be an object`);
    const slug = tool.slug;
    if (typeof slug !== "string" || !SLUG_RE.test(slug)) throw new CatalogError(`${where}.slug is invalid`);
    if (seen.has(slug)) throw new CatalogError(`duplicate slug "${slug}"`);
    seen.add(slug);
    for (const key of ["category", "title", "description", "icon"] as const) {
      if (typeof tool[key] !== "string" || tool[key] === "") throw new CatalogError(`${where}.${key} is missing`);
    }
    if (typeof tool.status !== "string" || !KNOWN_STATUSES.has(tool.status)) {
      throw new CatalogError(`${where}.status is invalid`);
    }
    if (!isStringArray(tool.input_kinds) || tool.input_kinds.length === 0) {
      throw new CatalogError(`${where}.input_kinds is invalid`);
    }
    if (!tool.input_kinds.every((k) => KNOWN_INPUT_KINDS.has(k))) {
      throw new CatalogError(`${where}.input_kinds has an unknown kind`);
    }
    if (!isStringArray(tool.accepts)) throw new CatalogError(`${where}.accepts is invalid`);
    if (tool.input_kinds.includes("file") && tool.accepts.length === 0) {
      throw new CatalogError(`${where} accepts files but lists no MIME types`);
    }
    if (typeof tool.min_inputs !== "number" || typeof tool.max_inputs !== "number" || tool.min_inputs > tool.max_inputs) {
      throw new CatalogError(`${where} has invalid min_inputs/max_inputs`);
    }
    const seo = tool.seo;
    if (!isRecord(seo) || typeof seo.title !== "string" || typeof seo.description !== "string" || !isStringArray(seo.keywords)) {
      throw new CatalogError(`${where}.seo is invalid`);
    }
  });

  return input as unknown as ToolCatalog;
}

export const catalog: ToolCatalog = parseCatalog(rawCatalog);

export const tools: readonly Tool[] = catalog.tools;
