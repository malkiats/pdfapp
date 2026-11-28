import type { MetadataRoute } from "next";
import { categoryHref } from "@/lib/config/categories";
import { guides } from "@/lib/content/guides";
import { absoluteUrl } from "@/lib/env";
import { getActiveCategories, getAllTools, toolHref } from "@/services/catalog";

/** Public, indexable pages. Dashboard and subscription are deliberately excluded (noindex). */
const STATIC_PATHS = [
  "/",
  "/tools",
  "/guides",
  "/pricing",
  "/about",
  "/contact",
  "/security",
  "/privacy",
  "/terms",
  "/accessibility",
  "/developers",
] as const;

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
  const guidePages: MetadataRoute.Sitemap = guides.map((guide) => ({
    url: absoluteUrl(`/guides/${guide.slug}`),
    changeFrequency: "monthly",
    priority: 0.6,
  }));
  return [...pages, ...categoryPages, ...toolPages, ...guidePages];
}
