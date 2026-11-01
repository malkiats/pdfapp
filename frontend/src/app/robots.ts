import type { MetadataRoute } from "next";
import { absoluteUrl } from "@/lib/env";

/**
 * Everything may be crawled. Private stubs (/dashboard, /subscription) carry a
 * noindex meta tag instead of a Disallow, so crawlers can actually see it.
 */
export default function robots(): MetadataRoute.Robots {
  return {
    rules: [{ userAgent: "*", allow: "/" }],
    sitemap: absoluteUrl("/sitemap.xml"),
  };
}
