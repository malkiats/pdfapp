/**
 * Metadata and JSON-LD helpers. Every page gets a unique title, description,
 * canonical URL and Open Graph block through `pageMetadata`.
 */
import type { Metadata } from "next";
import { absoluteUrl, siteUrl } from "@/lib/env";
import { siteConfig } from "@/lib/config/site";
import type { Tool, ToolFaqItem } from "@/types/catalog";

interface PageMetaInput {
  title: string;
  description: string;
  path: string;
  /** Use the title as-is instead of applying the "%s | Brand" template. */
  absoluteTitle?: boolean;
  noIndex?: boolean;
  keywords?: string[];
}

export function pageMetadata({ title, description, path, absoluteTitle, noIndex, keywords }: PageMetaInput): Metadata {
  const fullTitle = absoluteTitle ? title : `${title} | ${siteConfig.name}`;
  return {
    title: absoluteTitle ? { absolute: title } : title,
    description,
    keywords,
    alternates: { canonical: path },
    openGraph: {
      type: "website",
      siteName: siteConfig.name,
      title: fullTitle,
      description,
      url: path,
      locale: "en_US",
    },
    twitter: { card: "summary", title: fullTitle, description },
    robots: noIndex ? { index: false, follow: false } : undefined,
  };
}

export type JsonLd = Record<string, unknown>;

export function organizationJsonLd(): JsonLd {
  return {
    "@context": "https://schema.org",
    "@type": "Organization",
    "@id": `${siteUrl}/#organization`,
    name: siteConfig.name,
    url: absoluteUrl("/"),
  };
}

export function websiteJsonLd(): JsonLd {
  return {
    "@context": "https://schema.org",
    "@type": "WebSite",
    "@id": `${siteUrl}/#website`,
    name: siteConfig.name,
    url: absoluteUrl("/"),
    description: siteConfig.description,
    publisher: { "@id": `${siteUrl}/#organization` },
    inLanguage: "en",
  };
}

export function faqJsonLd(items: readonly ToolFaqItem[]): JsonLd {
  return {
    "@context": "https://schema.org",
    "@type": "FAQPage",
    mainEntity: items.map((item) => ({
      "@type": "Question",
      name: item.question,
      acceptedAnswer: { "@type": "Answer", text: item.answer },
    })),
  };
}

export function toolJsonLd(tool: Tool, path: string): JsonLd {
  return {
    "@context": "https://schema.org",
    "@type": "WebApplication",
    name: tool.title,
    description: tool.description,
    url: absoluteUrl(path),
    applicationCategory: "BusinessApplication",
    operatingSystem: "Any (web browser)",
    browserRequirements: "Requires a modern web browser with JavaScript enabled.",
    keywords: tool.seo.keywords.join(", "),
    publisher: { "@id": `${siteUrl}/#organization` },
    // Only a tool people can actually use today gets an offer; coming_soon tools must not claim one.
    ...(tool.status === "available"
      ? {
          isAccessibleForFree: ((tool as Record<string, unknown>).tier_required as string | undefined ?? "free") === "free",
          ...(((tool as Record<string, unknown>).tier_required as string | undefined ?? "free") === "free" ? { offers: { "@type": "Offer", price: "0", priceCurrency: "USD" } } : {}),
        }
      : {}),
  };
}

export function breadcrumbJsonLd(items: { name: string; path: string }[]): JsonLd {
  return {
    "@context": "https://schema.org",
    "@type": "BreadcrumbList",
    itemListElement: items.map((item, index) => ({
      "@type": "ListItem",
      position: index + 1,
      name: item.name,
      item: absoluteUrl(item.path),
    })),
  };
}

const LINE_SEPARATOR = new RegExp(String.fromCharCode(0x2028), "g");
const PARAGRAPH_SEPARATOR = new RegExp(String.fromCharCode(0x2029), "g");

/** Serialises JSON-LD safely for a <script> tag (prevents `</script>` breakout). */
export function serializeJsonLd(data: JsonLd | JsonLd[]): string {
  return JSON.stringify(data)
    .replace(/</g, "\\u003c")
    .replace(/>/g, "\\u003e")
    .replace(/&/g, "\\u0026")
    .replace(LINE_SEPARATOR, "\\u2028")
    .replace(PARAGRAPH_SEPARATOR, "\\u2029");
}
