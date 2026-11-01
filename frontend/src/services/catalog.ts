/**
 * Read-side queries over the bundled catalog. Server-only usage is expected
 * (pages, metadata, sitemap); client components receive `ToolSummary` props.
 */
import { tools } from "@/lib/catalog";
import { categories, categoryName, getCategoryById, type CategoryInfo } from "@/lib/config/categories";
import type { Tool, ToolSummary } from "@/types/catalog";

/** Tools featured on the homepage, in this order (slugs missing from the catalog are skipped). */
export const POPULAR_TOOL_SLUGS = [
  "merge-pdf",
  "split-pdf",
  "compress-pdf",
  "pdf-to-word",
  "word-to-pdf",
  "jpg-to-pdf",
  "pdf-to-jpg",
  "ocr-pdf",
  "image-to-text",
  "summarize-pdf",
  "protect-pdf",
  "compare-webpages",
] as const;

const bySlug = new Map<string, Tool>(tools.map((t) => [t.slug, t]));

export function getAllTools(): readonly Tool[] {
  return tools;
}

export function getToolBySlug(slug: string): Tool | undefined {
  return bySlug.get(slug);
}

export function getToolsInCategory(categoryId: string): Tool[] {
  return tools.filter((t) => t.category === categoryId);
}

export function getPopularTools(): Tool[] {
  return POPULAR_TOOL_SLUGS.map((s) => bySlug.get(s)).filter((t): t is Tool => t !== undefined);
}

export interface CategoryGroup {
  /** Undefined for tools whose category this frontend does not know yet. */
  category: CategoryInfo | undefined;
  tools: Tool[];
}

/** Known categories in display order (empty ones dropped), then any unknown ones grouped last. */
export function getToolsGroupedByCategory(): CategoryGroup[] {
  const groups: CategoryGroup[] = categories
    .map((category) => ({ category, tools: getToolsInCategory(category.id) }))
    .filter((g) => g.tools.length > 0);
  const unknown = tools.filter((t) => !getCategoryById(t.category));
  if (unknown.length > 0) groups.push({ category: undefined, tools: unknown });
  return groups;
}

/** Categories that currently contain at least one tool. */
export function getActiveCategories(): CategoryInfo[] {
  return categories.filter((c) => tools.some((t) => t.category === c.id));
}

export function toSummary(tool: Tool): ToolSummary {
  return {
    slug: tool.slug,
    title: tool.title,
    description: tool.description,
    category: tool.category,
    categoryName: categoryName(tool.category),
    keywords: tool.seo.keywords,
    status: tool.status,
  };
}

export function getToolSummaries(): ToolSummary[] {
  return tools.map(toSummary);
}

export function toolHref(tool: Pick<Tool, "slug">): string {
  return `/tools/${tool.slug}`;
}

export function hasFileInput(tool: Tool): boolean {
  return tool.input_kinds.includes("file");
}
