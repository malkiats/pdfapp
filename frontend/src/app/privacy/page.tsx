import Link from "next/link";
import { Container } from "@/components/ui/Container";
import { DraftNotice } from "@/components/ui/DraftNotice";
import { PageHeader } from "@/components/ui/PageHeader";
import { PlaceholderTag } from "@/components/ui/PlaceholderTag";
import { Prose } from "@/components/ui/Prose";
import { siteConfig } from "@/lib/config/site";
import { pageMetadata } from "@/lib/seo";

export const metadata = pageMetadata({
  title: "Privacy Policy (draft)",
  description: `The ${siteConfig.name} Privacy Policy is being drafted for legal review. Read how we handle files today.`,
  path: "/privacy",
});

export default function PrivacyPolicyPage() {
  return (
    <>
      <PageHeader eyebrow="Draft" title="Privacy Policy" />
      <Container className="space-y-8 py-12">
        <DraftNotice>
          <p className="font-semibold">This page is a draft placeholder, not a legal document.</p>
          <p className="mt-1">
            Our Privacy Policy will be drafted for review by a qualified lawyer before launch. Nothing on this page is
            the final policy.
          </p>
        </DraftNotice>
        <Prose>
          <h2>What the policy will cover</h2>
          <ul>
            <li>What data we process, why, and on what legal basis</li>
            <li>How long each kind of data is kept</li>
            <li>The service providers (sub-processors) that receive data and their own retention</li>
            <li>Your rights and how to exercise them</li>
            <li>Who we are and how to contact us</li>
          </ul>
          <h2>Until then</h2>
          <p>
            Our engineering approach to files is described in <Link href="/security">how we handle your files</Link>.
            Questions can go to <a href={`mailto:${siteConfig.privacyEmail}`}>{siteConfig.privacyEmail}</a>
            <PlaceholderTag />.
          </p>
        </Prose>
      </Container>
    </>
  );
}
