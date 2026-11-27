/**
 * Site-wide identity. `name` is a neutral PLACEHOLDER brand: change it here
 * and it changes everywhere (header, footer, metadata, JSON-LD, copy).
 */
import { categoryHref, getCategoryById } from "@/lib/config/categories";

const SITE_NAME = "Pagewell";

function publicEnv(value: string | undefined): string | undefined {
  const trimmed = value?.trim();
  return trimmed ? trimmed : undefined;
}

const ownerName = publicEnv(process.env.NEXT_PUBLIC_OWNER_NAME);
const rawEmail = publicEnv(process.env.NEXT_PUBLIC_CONTACT_EMAIL);
// Only a plain address is used in mailto: links.
const contactEmail = rawEmail && /^[^\s@<>"]+@[^\s@<>"]+\.[^\s@<>"]+$/.test(rawEmail) ? rawEmail : undefined;

export const siteConfig = {
  name: SITE_NAME,
  tagline: "Free Online PDF & Document Tools",
  /** The one default <title> (home page and fallback). */
  defaultTitle: "Pagewell: Free Online PDF & Document Tools - No Account Required",
  description:
    "Fast, simple document tools for everyone. Merge, split, compress, convert, OCR and summarize documents online. No account required. Your files are automatically deleted after processing.",
  /** AI provider named in consent and privacy copy (docs/privacy.md §3). */
  aiProviderName: "Groq",
  /**
   * Who runs the site and the one inbox for support, privacy and security.
   * Set in the hosting environment (Vercel → Environment Variables), not in this
   * public repository: NEXT_PUBLIC_OWNER_NAME and NEXT_PUBLIC_CONTACT_EMAIL.
   * Inlined at build time, so redeploy after changing them. While unset, the UI
   * shows example.com addresses tagged "Placeholder".
   */
  ownerName: ownerName ?? `the ${SITE_NAME} maintainer`,
  contactIsPlaceholder: !contactEmail,
  contactEmail: contactEmail ?? "hello@example.com",
  securityEmail: contactEmail ?? "security@example.com",
  privacyEmail: contactEmail ?? "privacy@example.com",
  /** Public source code (the site is open source). */
  sourceUrl: "https://github.com/malkiats/pdfapp",
  /** Date shown on the Privacy Policy and Terms; update it whenever either changes. */
  legalUpdated: "27 November 2026",
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
