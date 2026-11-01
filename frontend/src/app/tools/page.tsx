import Link from "next/link";
import { ToolSearch } from "@/components/tools/ToolSearch";
import { ToolGrid } from "@/components/tools/ToolGrid";
import { Container } from "@/components/ui/Container";
import { JsonLd } from "@/components/ui/JsonLd";
import { PageHeader } from "@/components/ui/PageHeader";
import { categoryHref } from "@/lib/config/categories";
import { breadcrumbJsonLd, pageMetadata } from "@/lib/seo";
import { getAllTools, getToolSummaries, getToolsGroupedByCategory } from "@/services/catalog";

export const metadata = pageMetadata({
  title: "All online PDF and document tools",
  description:
    "Browse every tool: organize, compress, convert, edit, protect, OCR and AI document tools. Files are deleted automatically after processing.",
  path: "/tools",
});

export default function ToolsPage() {
  const groups = getToolsGroupedByCategory();
  const total = getAllTools().length;
  return (
    <>
      <JsonLd
        data={breadcrumbJsonLd([
          { name: "Home", path: "/" },
          { name: "Tools", path: "/tools" },
        ])}
      />
      <PageHeader
        title="All tools"
        description={`${total} privacy-first tools for PDFs, images, Office files and web pages, grouped by what they do.`}
      >
        <div className="mt-6 max-w-2xl">
          <ToolSearch tools={getToolSummaries()} />
        </div>
        <nav aria-label="Categories" className="mt-6">
          <ul className="flex flex-wrap gap-2">
            {groups.map(({ category }) =>
              category ? (
                <li key={category.id}>
                  <a
                    href={`#${category.slug}`}
                    className="inline-flex min-h-11 items-center rounded-full border border-border bg-bg px-4 text-sm hover:border-accent"
                  >
                    {category.name}
                  </a>
                </li>
              ) : null,
            )}
          </ul>
        </nav>
      </PageHeader>
      <Container className="space-y-14 py-12">
        {groups.map(({ category, tools }) => {
          const id = category?.slug ?? "more-tools";
          return (
            <section key={id} id={id} aria-labelledby={`${id}-title`}>
              <div className="mb-5 flex flex-wrap items-end justify-between gap-2">
                <div>
                  <h2 id={`${id}-title`} className="text-2xl font-bold tracking-tight">
                    {category?.name ?? "More tools"}
                  </h2>
                  {category ? <p className="mt-1 text-muted">{category.summary}</p> : null}
                </div>
                {category ? (
                  <Link href={categoryHref(category)} className="inline-flex min-h-11 items-center text-sm font-medium text-accent hover:underline">
                    More about {category.name}
                  </Link>
                ) : null}
              </div>
              <ToolGrid tools={tools} />
            </section>
          );
        })}
      </Container>
    </>
  );
}
