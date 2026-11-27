import Link from "next/link";
import { Container } from "@/components/ui/Container";
import { PageHeader } from "@/components/ui/PageHeader";
import { PlaceholderTag } from "@/components/ui/PlaceholderTag";
import { Prose } from "@/components/ui/Prose";
import { siteConfig } from "@/lib/config/site";
import { pageMetadata } from "@/lib/seo";

export const metadata = pageMetadata({
  title: "Terms of Service",
  description: `The terms for using ${siteConfig.name}'s free online PDF and document tools.`,
  path: "/terms",
});

export default function TermsPage() {
  const email = siteConfig.contactEmail;
  return (
    <>
      <PageHeader title="Terms of Service" description={`Last updated: ${siteConfig.legalUpdated}`} />
      <Container className="py-12">
        <Prose>
          <h2>1. About these terms</h2>
          <p>
            These terms apply when you use {siteConfig.name}, a free, open-source set of online document tools run by{" "}
            {siteConfig.ownerName}. By using the site you agree to them. If you don&apos;t agree, please don&apos;t use
            the service.
          </p>

          <h2>2. The service</h2>
          <p>
            {siteConfig.name} is free to use and needs no account. We may add, change or remove tools, and change
            limits such as file size and page count, at any time. The service is provided on a best-effort basis and
            may sometimes be unavailable.
          </p>

          <h2>3. Your content</h2>
          <ul>
            <li>You keep all rights to the files and text you submit, and to the results.</li>
            <li>
              You give us permission to process your content only to produce the result you asked for, as described in
              our <Link href="/privacy">Privacy Policy</Link>.
            </li>
            <li>
              You confirm you have the right to use the content you submit, including permission to process any personal
              data about other people that it contains.
            </li>
            <li>Keep your own copies of important documents. We don&apos;t keep backups of your files.</li>
          </ul>

          <h2>4. Acceptable use</h2>
          <p>You must not use the service to:</p>
          <ul>
            <li>break any law or infringe anyone else&apos;s rights, including copyright and privacy;</li>
            <li>remove protection from documents you are not entitled to unlock;</li>
            <li>process illegal content, malware, or files designed to harm our systems;</li>
            <li>
              overload, probe or attack the service, get around its limits, or access it automatically at a scale that
              affects other users;
            </li>
            <li>make our server fetch web addresses you are not allowed to access.</li>
          </ul>
          <p>We may block access that breaks these rules.</p>

          <h2>5. AI tools</h2>
          <p>
            AI tools send your content to our AI provider, {siteConfig.aiProviderName}, only after you agree for that
            request. AI-generated summaries, translations and answers can be incomplete or wrong. Check them before you
            rely on them, especially for legal, medical, financial or other important decisions.
          </p>

          <h2>6. Open source</h2>
          <p>
            The source code is available on <a href={siteConfig.sourceUrl}>GitHub</a>. These terms cover your use of
            this hosted website, not the source code.
          </p>

          <h2>7. No warranty</h2>
          <p>
            The service is provided &quot;as is&quot; and &quot;as available&quot;, without warranties of any kind. We
            don&apos;t guarantee that results will be accurate, complete or suitable for your purpose, or that the
            service will be uninterrupted or error-free.
          </p>

          <h2>8. Limitation of liability</h2>
          <p>
            To the extent the law allows, we are not liable for any indirect or consequential loss, or for loss of data,
            profits or business, arising from your use of the service. Because the service is free, our total liability
            is limited to the maximum extent permitted by law. Nothing in these terms limits liability that cannot be
            limited by law.
          </p>

          <h2>9. Changes to these terms</h2>
          <p>
            We may update these terms. The date at the top shows when they last changed. If you keep using the service
            after a change, the updated terms apply.
          </p>

          <h2>10. Contact</h2>
          <p>
            Questions about these terms: <a href={`mailto:${email}`}>{email}</a>
            <PlaceholderTag />.
          </p>
        </Prose>
      </Container>
    </>
  );
}
