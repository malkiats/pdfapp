import Link from "next/link";
import { Container } from "@/components/ui/Container";
import { DraftNotice } from "@/components/ui/DraftNotice";
import { PageHeader } from "@/components/ui/PageHeader";
import { Prose } from "@/components/ui/Prose";
import { siteConfig } from "@/lib/config/site";
import { pageMetadata } from "@/lib/seo";

export const metadata = pageMetadata({
  title: "Terms of Service (draft)",
  description: `The ${siteConfig.name} Terms of Service are being drafted for legal review.`,
  path: "/terms",
});

export default function TermsPage() {
  return (
    <>
      <PageHeader eyebrow="Draft" title="Terms of Service" />
      <Container className="space-y-8 py-12">
        <DraftNotice>
          <p className="font-semibold">This page is a draft placeholder, not a legal document.</p>
          <p className="mt-1">
            Our Terms of Service will be drafted for review by a qualified lawyer before launch. Nothing on this page
            forms an agreement.
          </p>
        </DraftNotice>
        <Prose>
          <h2>What the terms will cover</h2>
          <ul>
            <li>Using the tools and acceptable use</li>
            <li>Plans, billing, renewals and refunds</li>
            <li>Your content and responsibility for it</li>
            <li>Availability, limits of liability and changes to the service</li>
          </ul>
          <p>
            Questions in the meantime? <Link href="/contact">Contact us</Link>.
          </p>
        </Prose>
      </Container>
    </>
  );
}
