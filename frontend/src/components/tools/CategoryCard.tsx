import Link from "next/link";
import { ArrowRight } from "lucide-react";
import { categoryHref, type CategoryInfo } from "@/lib/config/categories";
import { ToolIcon } from "./ToolIcon";

export function CategoryCard({ category, toolCount }: { category: CategoryInfo; toolCount: number }) {
  return (
    <article className="relative flex h-full flex-col rounded-xl border border-border bg-bg p-5 transition-colors hover:border-accent focus-within:ring-2 focus-within:ring-ring focus-within:ring-offset-2 focus-within:ring-offset-bg">
      <span className="inline-flex size-10 items-center justify-center rounded-lg bg-accent-soft text-accent-soft-fg">
        <ToolIcon name={category.icon} />
      </span>
      <h3 className="mt-4 font-semibold">
        <Link href={categoryHref(category)} className="after:absolute after:inset-0 after:rounded-xl focus:outline-none">
          {category.name}
        </Link>
      </h3>
      <p className="mt-1 flex-1 text-sm text-muted">{category.summary}</p>
      <p className="mt-4 inline-flex items-center gap-1 text-sm font-medium text-accent">
        {toolCount} {toolCount === 1 ? "tool" : "tools"}
        <ArrowRight aria-hidden="true" className="size-4" />
      </p>
    </article>
  );
}
