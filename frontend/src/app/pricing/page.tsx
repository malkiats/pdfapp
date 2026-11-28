import Link from "next/link";
import { Container } from "@/components/ui/Container";
import { PageHeader } from "@/components/ui/PageHeader";
import { siteConfig } from "@/lib/config/site";
import { pageMetadata } from "@/lib/seo";

export const metadata = pageMetadata({
  title: "Pricing - Completely Free & Open Source",
  description: "All PDF tools are completely free to use. No account required. Open source and privacy-first.",
  path: "/pricing",
});

export default function PricingPage() {
  return (
    <>
      <PageHeader
        title="Completely Free & Open Source"
        description="All tools are free to use. No account required. Privacy-first and open source."
      />
      <Container className="py-12">
        <div className="mb-8 rounded-lg border border-border bg-surface px-4 py-3 text-sm">
          <h2 className="font-semibold mb-2">✨ 100% Free & Open Source</h2>
          <p className="text-muted">
            Every tool is completely free to use, with no paywalls, no hidden charges, and no account required.
            The entire codebase is open source on GitHub, so you can self-host it or contribute improvements.
          </p>
        </div>

        <section aria-labelledby="features-title" className="mt-16">
          <h2 id="features-title" className="text-2xl font-bold tracking-tight">
            What&apos;s included
          </h2>
          <div className="mt-8 grid gap-8 md:grid-cols-2">
            <div>
              <h3 className="font-semibold mb-2">No Account Needed</h3>
              <p className="text-sm text-muted">Start using tools immediately without creating an account or providing any personal information.</p>
            </div>
            <div>
              <h3 className="font-semibold mb-2">Generous Limits</h3>
              <p className="text-sm text-muted">Files up to 100 MB and documents up to 2,000 pages, with no daily caps.</p>
            </div>
            <div>
              <h3 className="font-semibold mb-2">Privacy First</h3>
              <p className="text-sm text-muted">Files are deleted automatically after processing. We never keep your files or use them to train AI models.</p>
            </div>
            <div>
              <h3 className="font-semibold mb-2">Open Source</h3>
              <p className="text-sm text-muted">Full source code available. Self-host it, contribute improvements, or deploy to your own infrastructure.</p>
            </div>
            <div>
              <h3 className="font-semibold mb-2">All Tools Included</h3>
              <p className="text-sm text-muted">Access every tool: PDF editing, conversions, OCR, compression, signing, and more.</p>
            </div>
            <div>
              <h3 className="font-semibold mb-2">No Ads or Tracking</h3>
              <p className="text-sm text-muted">Clean, ad-free experience. No analytics tracking or third-party scripts.</p>
            </div>
          </div>
        </section>

        <section aria-labelledby="commitment-title" className="mt-16 grid gap-8 md:grid-cols-2">
          <div className="rounded-2xl border border-border p-6">
            <h2 id="commitment-title" className="text-xl font-semibold">
              Our free-forever commitment
            </h2>
            <ul className="mt-4 list-disc space-y-2 pl-5 text-sm text-muted">
              <li>Every tool on this site is free to use, with no account and no trial period.</li>
              <li>No ads, no tracking, and we never sell your data.</li>
              <li>The code stays open source, so the tools can never be locked away.</li>
            </ul>
          </div>
          <div className="rounded-2xl border border-border p-6">
            <h2 className="text-xl font-semibold">Need more than the free limits?</h2>
            <p className="mt-4 text-sm text-muted">
              The hosted site has fair-use limits (file size, pages and requests per minute) so it stays fast for
              everyone. For heavy or business use, run your own copy: you set the limits and decide where files are
              processed. Developers can also call the tools from their own scripts.
            </p>
            <div className="mt-4 flex flex-wrap gap-4 text-sm font-medium">
              <a href={siteConfig.sourceUrl} className="text-accent underline underline-offset-4">
                Self-host from GitHub
              </a>
              <Link href="/developers" className="text-accent underline underline-offset-4">
                API for developers
              </Link>
            </div>
          </div>
        </section>

        <section aria-labelledby="get-started-title" className="mt-16 max-w-3xl rounded-lg border border-border bg-surface p-8">
          <h2 id="get-started-title" className="text-2xl font-bold tracking-tight">
            Get Started
          </h2>
          <p className="mt-4 text-muted">
            Everything is free and ready to use now. Check out our tools to see what you can do with PDFs and documents.
          </p>
          <div className="mt-6 flex gap-4">
            <Link href="/tools" className="inline-flex min-h-11 items-center rounded-lg bg-accent px-6 font-medium text-accent-fg hover:bg-accent-hover">
              Explore All Tools
            </Link>
            <Link href="/guides" className="inline-flex min-h-11 items-center font-medium text-accent underline underline-offset-4">
              Read the guides
            </Link>
          </div>
        </section>
      </Container>
    </>
  );
}
