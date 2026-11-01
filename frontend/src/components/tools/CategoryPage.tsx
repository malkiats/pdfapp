import Link from "next/link";
import { Breadcrumbs } from "@/components/ui/Breadcrumbs";
import { Container } from "@/components/ui/Container";
import { JsonLd } from "@/components/ui/JsonLd";
import { categoryHref, type CategoryInfo } from "@/lib/config/categories";
import { retentionSentence } from "@/lib/config/retention";
import { absoluteUrl } from "@/lib/env";
import { breadcrumbJsonLd } from "@/lib/seo";
import { getActiveCategories, getToolsInCategory, toolHref } from "@/services/catalog";
import { ToolGrid } from "./ToolGrid";
import { ToolIcon } from "./ToolIcon";

export function CategoryPage({ category }: { category: CategoryInfo }) {
  const tools = getToolsInCategory(category.id);
  const path = categoryHref(category);
  const crumbs = [
    { name: "Home", path: "/" },
    { name: "Tools", path: "/tools" },
    { name: category.name, path },
  ];
  const others = getActiveCategories().filter((c) => c.id !== category.id);
  const itemList = {
    "@context": "https://schema.org",
    "@type": "ItemList",
    name: category.name,
    itemListElement: tools.map((tool, index) => ({
      "@type": "ListItem",
      position: index + 1,
      name: tool.title,
      url: absoluteUrl(toolHref(tool)),
    })),
  };

  return (
    <>
      <JsonLd data={[breadcrumbJsonLd(crumbs), itemList]} />
      <div className="border-b border-border bg-surface">
        <Container className="py-10 sm:py-14">
          <Breadcrumbs items={crumbs} />
          <div className="flex items-center gap-4">
            <span className="inline-flex size-12 items-center justify-center rounded-xl bg-accent-soft text-accent-soft-fg">
              <ToolIcon name={category.icon} className="size-6" />
            </span>
            <h1 className="text-3xl font-bold tracking-tight sm:text-4xl">{category.name}</h1>
          </div>
          <p className="mt-4 max-w-3xl text-lg text-muted">{category.intro}</p>
          <p className="mt-3 max-w-3xl text-sm text-muted">{retentionSentence}</p>
        </Container>
      </div>
      <Container className="py-12">
        <h2 className="sr-only">Tools in {category.name}</h2>
        <ToolGrid tools={tools} />
      </Container>
      <section aria-labelledby="other-categories" className="border-t border-border">
        <Container className="py-12">
          <h2 id="other-categories" className="text-xl font-semibold">
            Other categories
          </h2>
          <ul className="mt-4 flex flex-wrap gap-2">
            {others.map((c) => (
              <li key={c.id}>
                <Link
                  href={categoryHref(c)}
                  className="inline-flex min-h-11 items-center rounded-full border border-border px-4 text-sm hover:border-accent"
                >
                  {c.name}
                </Link>
              </li>
            ))}
          </ul>
        </Container>
      </section>
    </>
  );
}
