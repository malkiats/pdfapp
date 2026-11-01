import type { ToolSummary } from "@/types/catalog";

/** Lower-cases, strips accents and collapses punctuation to spaces. */
export function normalize(text: string): string {
  return text
    .normalize("NFKD")
    .replace(/\p{M}/gu, "")
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, " ")
    .trim();
}

function score(tool: ToolSummary, terms: string[]): number {
  const title = normalize(tool.title);
  const phrase = terms.join(" ");
  const slug = normalize(tool.slug);
  const keywords = normalize(tool.keywords.join(" "));
  const rest = normalize(`${tool.description} ${tool.categoryName}`);
  let total = 0;
  for (const term of terms) {
    let best = 0;
    if (title.split(" ").some((w) => w.startsWith(term))) best = 5;
    else if (title.includes(term) || slug.includes(term)) best = 4;
    else if (keywords.includes(term)) best = 3;
    else if (rest.includes(term)) best = 1;
    if (best === 0) return 0; // every term must match somewhere
    total += best;
  }
  // Word order matters for conversions: "pdf to word" should rank PDF to Word above Word to PDF.
  if (terms.length > 1 && (title.includes(phrase) || slug.includes(phrase))) total += 10;
  return total;
}

/**
 * Client-side catalog filter. Every whitespace-separated term must match the
 * title, slug, keywords, description or category; results are ranked by where
 * they matched, ties keep catalog order.
 */
export function searchTools(tools: readonly ToolSummary[], query: string, limit = 8): ToolSummary[] {
  const terms = normalize(query).split(" ").filter(Boolean);
  if (terms.length === 0) return [];
  return tools
    .map((tool, index) => ({ tool, index, score: score(tool, terms) }))
    .filter((r) => r.score > 0)
    .sort((a, b) => b.score - a.score || a.index - b.index)
    .slice(0, limit)
    .map((r) => r.tool);
}
