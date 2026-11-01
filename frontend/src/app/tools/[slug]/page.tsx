import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { ToolPage } from "@/components/tools/ToolPage";
import { pageMetadata } from "@/lib/seo";
import { getAllTools, getToolBySlug, toolHref } from "@/services/catalog";

/** One statically generated landing page per catalog tool, at the URL the contract documents. */
export function generateStaticParams(): { slug: string }[] {
  return getAllTools().map((tool) => ({ slug: tool.slug }));
}

export async function generateMetadata({ params }: PageProps<"/tools/[slug]">): Promise<Metadata> {
  const tool = getToolBySlug((await params).slug);
  if (!tool) return {};
  return pageMetadata({
    title: tool.seo.title,
    absoluteTitle: true,
    description: tool.seo.description,
    keywords: tool.seo.keywords,
    path: toolHref(tool),
  });
}

export default async function ToolRoute({ params }: PageProps<"/tools/[slug]">) {
  const tool = getToolBySlug((await params).slug);
  if (!tool) notFound();
  return <ToolPage tool={tool} />;
}
