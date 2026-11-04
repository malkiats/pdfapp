import Link from "next/link";
import { Container } from "@/components/ui/Container";
import { PageHeader } from "@/components/ui/PageHeader";
import { pageMetadata } from "@/lib/seo";

export const metadata = pageMetadata({
  title: "Pricing - Completely Free & Open Source",
  description: "All PDF tools are completely free to use with no limits. No account required. Open source and privacy-first.",
  path: "/pricing",
});

export default function PricingPage() {
  return (
    <>
      <PageHeader
        title="Completely Free & Open Source"
        description="All tools are free to use with no limits. No account required. Privacy-first and open source."
      />
      <Container className="py-12">
        <div className="mb-8 rounded-lg border border-border bg-surface px-4 py-3 text-sm">
          <h2 className="font-semibold mb-2">✨ 100% Free & Open Source</h2>
          <p className="text-muted">
            Every tool is completely free to use, with no limits, no hidden charges, and no account required.
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
              <h3 className="font-semibold mb-2">No File Size Limits</h3>
              <p className="text-sm text-muted">Process files of any size. Our generous limits grow as you need them.</p>
            </div>
            <div>
              <h3 className="font-semibold mb-2">Privacy First</h3>
              <p className="text-sm text-muted">Files are deleted automatically after processing. We never store or use your data for training.</p>
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

        <section aria-labelledby="get-started-title" className="mt-16 max-w-3xl rounded-lg border border-border bg-surface p-8">
          <h2 id="get-started-title" className="text-2xl font-bold tracking-tight">
            Get Started
          </h2>
          <p className="mt-4 text-muted">
            Everything is free and ready to use now. Check out our tools to see what you can do with PDFs and documents.
          </p>
          <div className="mt-6 flex gap-4">
            <Link href="/tools" className="inline-flex min-h-11 items-center rounded-lg bg-accent px-6 font-medium text-accent-foreground">
              Explore All Tools
            </Link>
            <a href="https://github.com" className="inline-flex min-h-11 items-center font-medium text-accent underline underline-offset-4">
              View on GitHub
            </a>
          </div>
        </section>
      </Container>
    </>
  );
}
