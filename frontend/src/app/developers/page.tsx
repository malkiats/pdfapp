import Link from "next/link";
import { Container } from "@/components/ui/Container";
import { PageHeader } from "@/components/ui/PageHeader";
import { Prose } from "@/components/ui/Prose";
import { siteConfig } from "@/lib/config/site";
import { apiBaseUrl } from "@/lib/env";
import { pageMetadata } from "@/lib/seo";

export const metadata = pageMetadata({
  title: "Developers: the document tools API",
  description: `Call ${siteConfig.name}'s PDF and document tools from your own scripts with a simple HTTP API, or self-host the open-source code.`,
  path: "/developers",
});

const codeClass = "block max-w-full overflow-x-auto rounded-xl border border-border bg-surface p-4 text-sm leading-6 text-fg";

export default function DevelopersPage() {
  const api = apiBaseUrl;
  const specUrl = `${siteConfig.sourceUrl}/blob/main/shared/openapi.yaml`;
  return (
    <>
      <PageHeader
        title="Developers"
        description="Every tool on this site is a plain HTTP endpoint. Use it from scripts and automations, or run your own copy."
      />
      <Container className="py-12">
        <Prose>
          <h2>Run a tool</h2>
          <p>
            Send a <code>multipart/form-data</code> POST to <code>{api}/api/v1/&#123;tool&#125;</code>, where the tool is
            the last part of its page address (for example <code>compress-pdf</code>). The response body is the result
            file, or the text for text tools.
          </p>
          <pre className={codeClass}>
            <code>{`curl -X POST ${api}/api/v1/compress-pdf \\
  -F "files=@report.pdf" \\
  -F 'options={"level":"medium"}' \\
  -o report-compressed.pdf`}</code>
          </pre>
          <h3>Form fields</h3>
          <ul>
            <li>
              <code>files</code>: one or more files (repeat the field for tools that take several, such as{" "}
              <code>merge-pdf</code>).
            </li>
            <li>
              <code>options</code>: a JSON object with the tool&apos;s options, e.g. <code>{`{"pages":"1-3"}`}</code>.
            </li>
            <li>
              <code>text</code>, <code>url_a</code>, <code>url_b</code>: for tools that take text or web addresses.
            </li>
            <li>
              <code>ai_consent=true</code>: required by the AI and image to text tools. Setting it means you agree to
              send the content to our AI provider, {siteConfig.aiProviderName}.
            </li>
          </ul>
          <h3>Another example: summarize a PDF</h3>
          <pre className={codeClass}>
            <code>{`curl -X POST ${api}/api/v1/summarize-pdf \\
  -F "files=@contract.pdf" \\
  -F 'options={"length":"short"}' \\
  -F "ai_consent=true"`}</code>
          </pre>

          <h2>List the tools</h2>
          <p>
            <code>GET {api}/api/v1/tools</code> returns every tool with its accepted file types, input counts and status,
            plus the current size limits. <code>GET {api}/api/v1/tools/&#123;tool&#125;</code> returns one tool.
          </p>

          <h2>Errors</h2>
          <p>
            Errors use the standard <code>application/problem+json</code> format (RFC 9457), with a stable{" "}
            <code>code</code> such as <code>unsupported_type</code>, <code>too_many_pages</code> or{" "}
            <code>rate_limited</code>, and a <code>request_id</code> to quote if you contact us.
          </p>

          <h2>Limits and fair use</h2>
          <ul>
            <li>About 4 MB per request through this API, and up to 100 pages per PDF.</li>
            <li>60 requests per minute per IP address (5 per minute for large-file uploads).</li>
            <li>
              AI tools share a limited capacity with everyone using the site. Expect occasional <code>rate_limited</code>{" "}
              responses; honour the <code>Retry-After</code> header.
            </li>
            <li>
              There is no API key and no guaranteed uptime. Automated use must follow our{" "}
              <Link href="/terms">Terms of Service</Link> and not affect other users.
            </li>
          </ul>

          <h2>Full specification and self-hosting</h2>
          <p>
            The complete API is described in an <a href={specUrl}>OpenAPI specification</a>. For heavy or business use,
            run your own copy: the <a href={siteConfig.sourceUrl}>source code</a> is open, so you control the limits and
            where your files are processed.
          </p>
        </Prose>
      </Container>
    </>
  );
}
