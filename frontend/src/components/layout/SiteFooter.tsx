import Link from "next/link";
import { ShieldCheck } from "lucide-react";
import { categoryHref } from "@/lib/config/categories";
import { companyLinks, siteConfig } from "@/lib/config/site";
import { retentionSentence } from "@/lib/config/retention";
import { getActiveCategories } from "@/services/catalog";

export function SiteFooter() {
  const categories = getActiveCategories();
  return (
    <footer className="mt-auto border-t border-border bg-surface">
      <div className="mx-auto max-w-6xl px-4 py-12 sm:px-6 lg:px-8">
        <div className="grid gap-10 md:grid-cols-[2fr_1fr_1fr]">
          <div>
            <p className="text-lg font-bold">{siteConfig.name}</p>
            <p className="mt-2 max-w-sm text-sm text-muted">{siteConfig.tagline}</p>
            <p className="mt-4 flex max-w-sm gap-2 text-sm text-muted">
              <ShieldCheck aria-hidden="true" className="mt-0.5 size-4 shrink-0 text-success" />
              <span>
                {retentionSentence} We never keep your original file names.{" "}
                <Link href="/security" className="inline-flex min-h-11 items-center text-accent underline underline-offset-4 md:min-h-0">
                  How we handle files
                </Link>
              </span>
            </p>
          </div>
          <nav aria-labelledby="footer-tools">
            <p id="footer-tools" className="text-sm font-semibold">
              Tools
            </p>
            <ul className="mt-3 space-y-0 text-sm md:space-y-2">
              {categories.map((category) => (
                <li key={category.id}>
                  <Link href={categoryHref(category)} className="inline-flex min-h-11 items-center text-muted hover:text-fg md:min-h-0">
                    {category.name}
                  </Link>
                </li>
              ))}
              <li>
                <Link href="/tools" className="inline-flex min-h-11 items-center text-muted hover:text-fg md:min-h-0">
                  All tools
                </Link>
              </li>
            </ul>
          </nav>
          <nav aria-labelledby="footer-company">
            <p id="footer-company" className="text-sm font-semibold">
              Open Source
            </p>
            <ul className="mt-3 space-y-0 text-sm md:space-y-2">
              <li>
                <a href="https://github.com" className="inline-flex min-h-11 items-center text-muted hover:text-fg md:min-h-0">
                  GitHub
                </a>
              </li>
              {companyLinks.map((link) => (
                <li key={link.href}>
                  <Link href={link.href} className="inline-flex min-h-11 items-center text-muted hover:text-fg md:min-h-0">
                    {link.label}
                  </Link>
                </li>
              ))}
            </ul>
          </nav>
        </div>
        <p className="mt-10 border-t border-border pt-6 text-xs text-muted">
          {siteConfig.name}. No analytics or advertising trackers run on this site.
        </p>
      </div>
    </footer>
  );
}
