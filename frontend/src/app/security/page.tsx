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
            Each task gets a random identifier and a private access token that only your browser receives, once. The
            token is kept in memory, not saved in your browser storage or put in a web address. Downloads use a
            single-use link that expires after about a minute.
          </p>
          <h2>Isolated processing</h2>
          <p>
            Documents are opened only by sandboxed workers with strict time and memory limits. The workers that handle
            your files have no route to the internet, and each task runs in a fresh process.
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
