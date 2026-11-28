import Link from "next/link";
import { Container } from "@/components/ui/Container";
import { PageHeader } from "@/components/ui/PageHeader";
import { Prose } from "@/components/ui/Prose";
import { retentionSentence } from "@/lib/config/retention";
import { siteConfig } from "@/lib/config/site";
import { pageMetadata } from "@/lib/seo";
import { getAllTools } from "@/services/catalog";

export const metadata = pageMetadata({
  title: "About us",
  description: `${siteConfig.name} builds privacy-first online document tools: useful everyday tools that do not keep your files.`,
  path: "/about",
});

export default function AboutPage() {
  const available = getAllTools().filter((t) => t.status === "available").length;
  return (
    <>
      <PageHeader title={`About ${siteConfig.name}`} description="Everyday document tools, built so that your files are not our business." />
      <Container className="py-12">
        <Prose>
          <h2>Why we exist</h2>
          <p>
            Merging a contract, shrinking a scan or pulling text out of a photo should not mean handing your documents
            to someone who keeps them. Many online tools are convenient but vague about what happens to your files
            afterwards. We wanted tools that are just as easy to use, with a clear, checkable answer to that question.
          </p>
          <h2>What we believe</h2>
          <ul>
            <li>
              <strong>Your files are yours.</strong> We hold them only while we process them and while you download the
              result. {retentionSentence}
            </li>
            <li>
              <strong>Honesty over slogans.</strong> We say exactly what we do and what we can&apos;t promise. See{" "}
              <Link href="/security">how we handle files</Link> for the details, including the limits.
            </li>
            <li>
              <strong>100% free and open source.</strong> No account required, no ads, no hidden charges, ever. Full
              source code available on GitHub for anyone to review, self-host, or contribute to.
            </li>
            <li>
              <strong>No ads, no tracking.</strong> We don&apos;t run analytics or advertising trackers on this site.
              We never sell or share your information. See our <Link href="/privacy">Privacy Policy</Link>.
            </li>
          </ul>
          <h2>What you can do today</h2>
          <p>
            {available} tools are ready to use right now, for free: organizing and editing PDFs, converting to and from
            Office formats and images, reading text from images, and AI summaries, translations and answers. A few more,
            such as redaction and form filling, are marked &quot;Coming soon&quot; until they work properly. We would
            rather ship fewer tools than ones that don&apos;t do what they say.
          </p>
          <h2>Get in touch</h2>
          <p>
            Questions, ideas or a tool you are missing? <Link href="/contact">Contact us</Link>.
          </p>
        </Prose>
      </Container>
    </>
  );
}
