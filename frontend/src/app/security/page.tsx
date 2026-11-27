import Link from "next/link";
import { PrivacyLimits, PrivacySteps } from "@/components/home/PrivacySteps";
import { Container } from "@/components/ui/Container";
import { PageHeader } from "@/components/ui/PageHeader";
import { PlaceholderTag } from "@/components/ui/PlaceholderTag";
import { Prose } from "@/components/ui/Prose";
import { retentionSentence } from "@/lib/config/retention";
import { siteConfig } from "@/lib/config/site";
import { pageMetadata } from "@/lib/seo";

export const metadata = pageMetadata({
  title: "Security and file handling",
  description: `How ${siteConfig.name} handles your files: isolated processing, automatic deletion, no file names in storage and no content in logs.`,
  path: "/security",
});

export default function SecurityPage() {
  return (
    <>
      <PageHeader title="How we handle your files" description={retentionSentence} />
      <Container className="space-y-12 py-12">
        <section aria-labelledby="lifecycle-title">
          <h2 id="lifecycle-title" className="mb-6 text-2xl font-bold tracking-tight">
            The life of a file
          </h2>
          <PrivacySteps />
        </section>
        <PrivacyLimits />
        <Prose>
          <h2>Access to your results</h2>
          <p>
            Most files are sent with your request and the result comes back in the response. Large files are uploaded
            and downloaded through short-lived signed links that only your browser receives. Your uploaded files are
            deleted right after processing, and the result shortly after you download it. Automatic cleanup removes
            anything left over, and a storage rule deletes any leftovers after at most 24 hours.
          </p>
          <h2>Isolated processing</h2>
          <p>
            Each request is handled on its own by our processing service, with strict time, size and page limits. Files
            are kept in memory and in a private temporary folder that is deleted when the request ends, whether it
            succeeded or failed. Nothing from one request is available to another.
          </p>
          <h2>AI tools</h2>
          <p>
            AI tools send your content to our AI provider, {siteConfig.aiProviderName}, only after you tick the consent
            box for that request. For scanned PDFs, images of the first pages are sent so the text can be read. We
            don&apos;t store prompts or answers. See the <Link href="/privacy">Privacy Policy</Link> for details.
          </p>
          <h2>This website</h2>
          <p>
            This site loads no third-party scripts, runs no analytics or advertising trackers, and sends strict security
            headers, including a Content Security Policy that only allows connections to our own services.
          </p>
          <h2>Reporting a vulnerability</h2>
          <p>
            Please report security issues privately to <a href={`mailto:${siteConfig.securityEmail}`}>{siteConfig.securityEmail}</a>
            <PlaceholderTag />.
            See also our <Link href="/privacy">privacy policy</Link>.
          </p>
        </Prose>
      </Container>
    </>
  );
}
