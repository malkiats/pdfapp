import Link from "next/link";
import { ArrowRight } from "lucide-react";
import { homeFaq } from "@/components/home/faq";
import { Hero } from "@/components/home/Hero";
import { PrivacyLimits, PrivacySteps } from "@/components/home/PrivacySteps";
import { Section } from "@/components/home/Section";
import { WhyChooseUs } from "@/components/home/WhyChooseUs";
import { PricingCards } from "@/components/pricing/PricingCards";
import { CategoryCard } from "@/components/tools/CategoryCard";
import { ToolGrid } from "@/components/tools/ToolGrid";
import { Faq } from "@/components/ui/Faq";
import { JsonLd } from "@/components/ui/JsonLd";
import { retentionSentence } from "@/lib/config/retention";
import { siteConfig } from "@/lib/config/site";
import { faqJsonLd, organizationJsonLd, pageMetadata, websiteJsonLd } from "@/lib/seo";
import { getActiveCategories, getPopularTools, getToolSummaries, getToolsInCategory } from "@/services/catalog";

export const metadata = pageMetadata({
  title: siteConfig.defaultTitle,
  absoluteTitle: true,
  description: `Merge, split, compress, convert and OCR documents online. ${retentionSentence}`,
  path: "/",
});

const linkClass = "inline-flex min-h-11 items-center gap-1 text-sm font-medium text-accent hover:underline";

export default function HomePage() {
  const summaries = getToolSummaries();
  const popular = getPopularTools();
  const categories = getActiveCategories();

  return (
    <>
      <JsonLd data={[organizationJsonLd(), websiteJsonLd(), faqJsonLd(homeFaq)]} />
      <Hero tools={summaries} />

      <Section
        id="popular"
        title="Popular tools"
        description="The everyday document tasks people need most."
        action={
          <Link href="/tools" className={linkClass}>
            All tools <ArrowRight aria-hidden="true" className="size-4" />
          </Link>
        }
      >
        <ToolGrid tools={popular} badgeVariant="subtle" />
      </Section>

      <Section id="categories" title="Tool categories" description="Find the right tool by what you want to do." muted>
        <ul className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {categories.map((category) => (
            <li key={category.id}>
              <CategoryCard category={category} toolCount={getToolsInCategory(category.id).length} />
            </li>
          ))}
        </ul>
      </Section>

      <Section
        id="privacy"
        title="How we handle your files"
        description="Privacy is not a setting you have to find. This is what happens to every file, every time."
        action={
          <Link href="/security" className={linkClass}>
            Security details <ArrowRight aria-hidden="true" className="size-4" />
          </Link>
        }
      >
        <PrivacySteps />
        <div className="mt-6">
          <PrivacyLimits />
        </div>
      </Section>

      <Section id="why" title={`Why choose ${siteConfig.name}`} muted>
        <WhyChooseUs />
      </Section>

      <Section
        id="pricing"
        title="Simple pricing"
        description="Start free. Upgrade only if you need bigger files."
        action={
          <Link href="/pricing" className={linkClass}>
            Compare plans <ArrowRight aria-hidden="true" className="size-4" />
          </Link>
        }
      >
        <PricingCards />
      </Section>

      <Section id="faq" title="Frequently asked questions" muted>
        <div className="max-w-3xl">
          <Faq items={homeFaq} />
        </div>
      </Section>
    </>
  );
}
