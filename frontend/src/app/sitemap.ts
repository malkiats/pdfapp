import type { MetadataRoute } from "next";
import { categoryHref } from "@/lib/config/categories";
import { absoluteUrl } from "@/lib/env";
import { getActiveCategories, getAllTools, toolHref } from "@/services/catalog";

/** Public, indexable pages. Dashboard and subscription are deliberately excluded (noindex). */
const STATIC_PATHS = ["/", "/tools", "/pricing", "/about", "/contact", "/security", "/privacy", "/terms"] as const;

export default function sitemap(): MetadataRoute.Sitemap {
  const pages: MetadataRoute.Sitemap = STATIC_PATHS.map((path) => ({
    url: absoluteUrl(path),
    changeFrequency: "weekly",
    priority: path === "/" ? 1 : path === "/tools" ? 0.9 : 0.5,
  }));
  const categoryPages: MetadataRoute.Sitemap = getActiveCategories().map((category) => ({
    url: absoluteUrl(categoryHref(category)),
    changeFrequency: "weekly",
    priority: 0.8,
  }));
  const toolPages: MetadataRoute.Sitemap = getAllTools().map((tool) => ({
    url: absoluteUrl(toolHref(tool)),
    changeFrequency: "weekly",
    priority: 0.7,
  }));
  return [...pages, ...categoryPages, ...toolPages];
}
