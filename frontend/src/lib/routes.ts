import { tools } from "@/lib/catalog";
import { categories } from "@/lib/config/categories";

/** Returns the set of slugs, throwing at build time if the namespace has a duplicate. */
export function uniqueSlugs(slugs: readonly string[], namespace: string): ReadonlySet<string> {
  const set = new Set<string>();
  for (const slug of slugs) {
    if (set.has(slug)) throw new Error(`Slug collision in ${namespace}: "${slug}"`);
    set.add(slug);
  }
  return set;
}

/** Slugs served at /tools/{slug}: one per catalog tool. */
export const toolRouteSlugs = uniqueSlugs(
  tools.map((t) => t.slug),
  "/tools",
);

/** Slugs served at /categories/{slug}: categories that contain at least one tool. */
export const categoryRouteSlugs = uniqueSlugs(
  categories.filter((c) => tools.some((t) => t.category === c.id)).map((c) => c.slug),
  "/categories",
);

/** True when `pathname` is a prerendered /tools/{slug} or /categories/{slug} page. */
export function isKnownDynamicRoute(pathname: string): boolean {
  const match = /^\/(tools|categories)\/([^/]+)\/?$/.exec(pathname);
  if (!match) return false;
  const [, namespace, slug = ""] = match;
  return namespace === "tools" ? toolRouteSlugs.has(slug) : categoryRouteSlugs.has(slug);
}
