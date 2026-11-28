import Link from "next/link";
import { ArrowRight, BookOpen } from "lucide-react";
import { Container } from "@/components/ui/Container";
import { PageHeader } from "@/components/ui/PageHeader";
import { guides } from "@/lib/content/guides";
import { siteConfig } from "@/lib/config/site";
import { pageMetadata } from "@/lib/seo";

export const metadata = pageMetadata({
  title: "Guides: how to get things done with PDFs",
  description: `Step-by-step guides for common document tasks with ${siteConfig.name}: shrink, combine, summarize and copy text from files.`,
  path: "/guides",
});

export default function GuidesPage() {
  return (
    <>
      <PageHeader title="Guides" description="Short, step-by-step how-tos for everyday document tasks." />
      <Container className="py-12">
        <ul className="grid gap-6 md:grid-cols-2">
          {guides.map((guide) => (
            <li key={guide.slug}>
              <article className="group relative flex h-full flex-col rounded-2xl border border-border p-6 transition-colors hover:border-accent focus-within:ring-2 focus-within:ring-ring">
                <span className="inline-flex size-10 items-center justify-center rounded-lg bg-accent-soft text-accent-soft-fg">
                  <BookOpen aria-hidden="true" className="size-5" />
                </span>
                <h2 className="mt-4 text-lg font-semibold">
                  <Link href={`/guides/${guide.slug}`} className="after:absolute after:inset-0 after:rounded-2xl focus:outline-none">
                    {guide.title}
                  </Link>
                </h2>
                <p className="mt-1 flex-1 text-sm text-muted">{guide.description}</p>
                <span aria-hidden="true" className="mt-4 inline-flex items-center gap-1 text-sm font-medium text-accent">
                  Read the guide <ArrowRight className="size-4 transition-transform group-hover:translate-x-1" />
                </span>
              </article>
            </li>
          ))}
        </ul>
      </Container>
    </>
  );
}
