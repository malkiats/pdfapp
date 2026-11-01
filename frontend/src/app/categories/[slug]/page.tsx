import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { CategoryPage } from "@/components/tools/CategoryPage";
import { categoryHref } from "@/lib/config/categories";
import { pageMetadata } from "@/lib/seo";
import { getActiveCategories } from "@/services/catalog";

function findCategory(slug: string) {
  return getActiveCategories().find((c) => c.slug === slug);
}

/** One statically generated page per category that has tools. */
export function generateStaticParams(): { slug: string }[] {
  return getActiveCategories().map((category) => ({ slug: category.slug }));
}

export async function generateMetadata({ params }: PageProps<"/categories/[slug]">): Promise<Metadata> {
  const category = findCategory((await params).slug);
  if (!category) return {};
  return pageMetadata({ title: category.seoTitle, description: category.seoDescription, path: categoryHref(category) });
}

export default async function CategoryRoute({ params }: PageProps<"/categories/[slug]">) {
  const category = findCategory((await params).slug);
  if (!category) notFound();
  return <CategoryPage category={category} />;
}
