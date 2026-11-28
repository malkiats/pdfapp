import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { ArrowRight } from "lucide-react";
import { Breadcrumbs } from "@/components/ui/Breadcrumbs";
import { Container } from "@/components/ui/Container";
import { Faq } from "@/components/ui/Faq";
import { JsonLd } from "@/components/ui/JsonLd";
import { Prose } from "@/components/ui/Prose";
import { getGuide, guides } from "@/lib/content/guides";
import { breadcrumbJsonLd, faqJsonLd, pageMetadata } from "@/lib/seo";
import { getToolBySlug, toolHref } from "@/services/catalog";

export function generateStaticParams(): { slug: string }[] {
  return guides.map((guide) => ({ slug: guide.slug }));
}

export async function generateMetadata({ params }: PageProps<"/guides/[slug]">): Promise<Metadata> {
  const guide = getGuide((await params).slug);
  if (!guide) return {};
  return pageMetadata({ title: guide.title, description: guide.description, path: `/guides/${guide.slug}` });
}

export default async function GuideRoute({ params }: PageProps<"/guides/[slug]">) {
  const guide = getGuide((await params).slug);
  const tool = guide ? getToolBySlug(guide.toolSlug) : undefined;
  if (!guide || !tool) notFound();
  const path = `/guides/${guide.slug}`;
  const crumbs = [
    { name: "Home", path: "/" },
    { name: "Guides", path: "/guides" },
    { name: guide.title, path },
  ];
  const howTo = {
    "@context": "https://schema.org",
    "@type": "HowTo",
    name: guide.title,
    description: guide.description,
    step: guide.steps.map((step, i) => ({ "@type": "HowToStep", position: i + 1, name: step.title, text: step.text })),
  };
  const cta = (
    <Link
      href={toolHref(tool)}
      className="inline-flex min-h-11 items-center gap-2 rounded-lg bg-accent px-5 font-medium text-accent-fg hover:bg-accent-hover"
    >
      Open {tool.title} <ArrowRight aria-hidden="true" className="size-4" />
    </Link>
  );

  return (
    <>
      <JsonLd data={[howTo, breadcrumbJsonLd(crumbs), faqJsonLd(guide.faq)]} />
      <div className="border-b border-border bg-surface">
        <Container className="py-8 sm:py-12">
          <Breadcrumbs items={crumbs} />
          <h1 className="text-3xl font-bold tracking-tight sm:text-4xl">{guide.title}</h1>
          <p className="mt-3 max-w-2xl text-lg text-muted">{guide.intro}</p>
          <div className="mt-6">{cta}</div>
        </Container>
      </div>
      <Container className="py-12">
        <Prose>
          <h2>Step by step</h2>
          <ol>
            {guide.steps.map((step) => (
              <li key={step.title}>
                <strong>{step.title}.</strong> {step.text}
              </li>
            ))}
          </ol>
          <h2>Tips</h2>
          <ul>
            {guide.tips.map((tip) => (
              <li key={tip}>{tip}</li>
            ))}
          </ul>
        </Prose>
        <div className="mt-10 max-w-3xl">
          <h2 className="mb-4 text-2xl font-semibold">Questions</h2>
          <Faq items={guide.faq} />
        </div>
        <div className="mt-10">{cta}</div>
      </Container>
    </>
  );
}
