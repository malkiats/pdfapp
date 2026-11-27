import Link from "next/link";
import { Container } from "@/components/ui/Container";
import { PageHeader } from "@/components/ui/PageHeader";
import { PlaceholderTag } from "@/components/ui/PlaceholderTag";
import { Prose } from "@/components/ui/Prose";
import { retentionSentence } from "@/lib/config/retention";
import { siteConfig } from "@/lib/config/site";
import { pageMetadata } from "@/lib/seo";

export const metadata = pageMetadata({
  title: "Privacy Policy",
  description: `How ${siteConfig.name} handles your files and data: what is processed, who receives it, how long it is kept and your rights.`,
  path: "/privacy",
});

// Must agree with docs/privacy.md (engineering privacy model).
export default function PrivacyPolicyPage() {
  const email = siteConfig.privacyEmail;
  return (
    <>
      <PageHeader title="Privacy Policy" description={`Last updated: ${siteConfig.legalUpdated}`} />
      <Container className="py-12">
        <Prose>
          <h2>Summary</h2>
          <ul>
            <li>You don&apos;t need an account. We don&apos;t ask for your name, email address or payment details.</li>
            <li>
              Your files are used only to produce the result you asked for. {retentionSentence} We don&apos;t keep
              copies, sell your data or use it to train AI models.
            </li>
            <li>AI tools send your content to our AI provider, {siteConfig.aiProviderName}, only after you agree to it for that request.</li>
            <li>We use no cookies for tracking, no analytics and no advertising.</li>
          </ul>

          <h2>1. Who we are</h2>
          <p>
            {siteConfig.name} is an open-source project run by {siteConfig.ownerName}, who is responsible for your
            data on this site (the &quot;data controller&quot;). You can reach us at{" "}
            <a href={`mailto:${email}`}>{email}</a>
            <PlaceholderTag />. The source code is public on <a href={siteConfig.sourceUrl}>GitHub</a>.
          </p>

          <h2>2. What we process and why</h2>
          <h3>Files, text and web addresses you submit</h3>
          <p>
            When you use a tool, we process the files, text or web addresses you provide only to produce your result.
            Most files are processed in memory within your request and deleted before the response is sent back. Files
            larger than about 4 MB are uploaded to temporary cloud storage, processed, and deleted as described in{" "}
            section 4. Original file names stay in your browser; results are given a generic name.
          </p>
          <p>
            For tools that compare web pages or summarize an article from a link, our server fetches the page at the
            address you give. That website will see a request from our server, not from you.
          </p>
          <h3>AI tools</h3>
          <p>
            The AI tools (such as Summarize, Translate, Ask PDF and PDF to Markdown) send the text of your document, or
            the text you typed, to {siteConfig.aiProviderName} to generate the answer. If a PDF is a scan with no text
            layer, images of its first pages are sent so that the text can be read. This only happens after you tick
            the consent box for that request. We don&apos;t store the prompts or the answers.
          </p>
          <h3>Technical data</h3>
          <p>
            Like any website, our hosting provider receives your IP address, browser type and the pages you request. We
            use IP addresses briefly, in memory, to limit how many requests one visitor can make, which protects the
            service from abuse. Our application logs contain only technical details such as the tool used, the
            response status, timing and an error reference. They never contain your file contents, file names,
            extracted text, AI prompts or answers, or the web addresses you submit.
          </p>
          <h3>Contacting us</h3>
          <p>
            If you email us, we use your email address and message only to reply, and delete them when they are no
            longer needed. Please don&apos;t attach the documents you were working on.
          </p>

          <h2>3. Legal basis</h2>
          <p>Where data protection laws such as the GDPR apply, we rely on:</p>
          <ul>
            <li>
              <strong>Providing the service you request</strong> for processing your files, text and web addresses.
            </li>
            <li>
              <strong>Your consent</strong> for sending content to our AI provider. You give it per request and can
              simply not use the AI tools.
            </li>
            <li>
              <strong>Legitimate interests</strong> in keeping the service secure and working, for technical logs and
              rate limiting.
            </li>
          </ul>

          <h2>4. How long we keep data</h2>
          <ul>
            <li>
              <strong>Files processed within a request:</strong> deleted before the response is sent back.
            </li>
            <li>
              <strong>Large files (temporary storage):</strong> inputs are deleted as soon as processing starts and
              results shortly after you download them. {retentionSentence} A storage safety rule removes anything left
              over after at most 24 hours.
            </li>
            <li>
              <strong>AI prompts and answers:</strong> not stored by us. {siteConfig.aiProviderName} handles them
              under its own policies (section 5).
            </li>
            <li>
              <strong>Technical logs:</strong> kept by our hosting provider for a limited period under its log
              retention, then deleted automatically.
            </li>
            <li>
              <strong>Emails:</strong> kept only as long as needed to deal with your request.
            </li>
          </ul>

          <h2>5. Service providers</h2>
          <p>We use these providers to run the service. Each processes data only as needed to provide its service.</p>
          <ul>
            <li>
              <strong>Vercel</strong> hosts the website and the processing servers, and handles every request,
              including the files you send. See the <a href="https://vercel.com/legal/privacy-policy">Vercel privacy policy</a>.
            </li>
            <li>
              <strong>Cloudflare (R2 storage)</strong> temporarily stores large files during processing. See the{" "}
              <a href="https://www.cloudflare.com/privacypolicy/">Cloudflare privacy policy</a>.
            </li>
            <li>
              <strong>{siteConfig.aiProviderName}</strong> runs the AI models, only for AI tools and only with your
              consent. See <a href="https://console.groq.com/docs/your-data">how Groq handles API data</a> and the{" "}
              <a href="https://groq.com/privacy-policy">Groq privacy policy</a>.
            </li>
          </ul>
          <p>
            These providers may process data outside your country, including in the United States. Where required, they
            use recognised safeguards such as Standard Contractual Clauses.
          </p>

          <h2>6. Cookies and browser storage</h2>
          <p>
            We don&apos;t use tracking, analytics or advertising cookies, and we load no third-party scripts. Your
            browser stores your light or dark theme preference locally; it never leaves your device.
          </p>

          <h2>7. Your rights</h2>
          <p>
            Depending on where you live, you may have the right to access, correct or delete your personal data, to
            object to or restrict its processing, to data portability, and to withdraw consent at any time. Because we
            don&apos;t keep accounts or your files, we usually hold no data that identifies you, except an email you
            sent us. To make a request, email <a href={`mailto:${email}`}>{email}</a>. You can also complain to your
            local data protection authority.
          </p>

          <h2>8. Security</h2>
          <p>
            Connections are encrypted (HTTPS), files are deleted automatically, and logs are restricted to technical
            fields. Read <Link href="/security">how we handle your files</Link> for details and the limits of what we
            can promise.
          </p>

          <h2>9. Children</h2>
          <p>
            The service is not directed at children under 16, and we don&apos;t knowingly collect their personal data.
          </p>

          <h2>10. Changes to this policy</h2>
          <p>
            If we change how we handle data, we will update this page and the date at the top. Significant changes will
            be highlighted on the site.
          </p>

          <h2>11. Contact</h2>
          <p>
            Questions about this policy or your data: <a href={`mailto:${email}`}>{email}</a>
            <PlaceholderTag />. See also our <Link href="/terms">Terms of Service</Link>.
          </p>
        </Prose>
      </Container>
    </>
  );
}
