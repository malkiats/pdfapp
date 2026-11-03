/**
 * Site-wide identity. `name` is a neutral PLACEHOLDER brand: change it here
 * and it changes everywhere (header, footer, metadata, JSON-LD, copy).
 */
import { categoryHref, getCategoryById } from "@/lib/config/categories";

export const siteConfig = {
  name: "Pagewell",
  tagline: "Free Online PDF & Document Tools",
  /** The one default <title> (home page and fallback). */
  defaultTitle: "Pagewell: Free Online PDF & Document Tools - No Account Required",
  description:
    "Fast, simple document tools for everyone. Merge, split, compress, convert, OCR and summarize documents online. No account required. Your files are automatically deleted after processing.",
  /** AI provider named in consent and privacy copy (docs/privacy.md §3). */
  aiProviderName: "Groq",
  /**
   * PLACEHOLDER addresses (example.com). Replacing them with real mailboxes is
   * a launch blocker; the UI tags them as placeholders while this is true.
   */
  contactIsPlaceholder: true,
  contactEmail: "hello@example.com",
  securityEmail: "security@example.com",
  privacyEmail: "privacy@example.com",
} as const;

function categoryLink(id: "ai" | "compare"): string {
  const category = getCategoryById(id);
  if (!category) throw new Error(`site.ts: missing category "${id}"`);
  return categoryHref(category);
}

/** Primary nav. Hrefs are derived from the category config/catalog (tested in tests/unit/routes.test.ts). */
export const mainNav: readonly { href: string; label: string }[] = [
  { href: categoryLink("ai"), label: "AI Tools" },
  { href: "/tools/compare-webpages", label: "Compare Webpages" },
  { href: "/about", label: "About" },
];

export const companyLinks = [
  { href: "/about", label: "About" },
  { href: "/security", label: "Security" },
  { href: "/privacy", label: "Privacy Policy" },
  { href: "/terms", label: "Terms" },
  { href: "/contact", label: "Contact" },
] as const;
