import Link from "next/link";
import { ArrowRight } from "lucide-react";
import { StatusBadge, type BadgeVariant } from "@/components/ui/StatusBadge";
import { toolHref } from "@/services/catalog";
import type { Tool } from "@/types/catalog";
import { ToolIcon } from "./ToolIcon";

export function ToolCard({
  tool,
  headingLevel = 3,
  badgeVariant = "default",
}: {
  tool: Tool;
  headingLevel?: 2 | 3;
  badgeVariant?: BadgeVariant;
}) {
  const Heading = headingLevel === 2 ? "h2" : "h3";
  return (
    <article className="group relative flex h-full flex-col rounded-xl border border-border bg-bg p-5 transition-all hover:-translate-y-0.5 hover:border-accent hover:shadow-md motion-reduce:transform-none focus-within:ring-2 focus-within:ring-ring focus-within:ring-offset-2 focus-within:ring-offset-bg">
      <div className="flex items-start justify-between gap-3">
        <span className="inline-flex size-10 items-center justify-center rounded-lg bg-accent-soft text-accent-soft-fg">
          <ToolIcon name={tool.icon} />
        </span>
        <StatusBadge status={tool.status} variant={badgeVariant} />
      </div>
      <Heading className="mt-4 font-semibold">
        <Link href={toolHref(tool)} className="after:absolute after:inset-0 after:rounded-xl focus:outline-none">
          {tool.title}
        </Link>
      </Heading>
      <p className="mt-1 text-sm text-muted">{tool.description}</p>
      {/* Visual cue only: the whole card is already the link (see the heading). */}
      <span aria-hidden="true" className="mt-auto inline-flex items-center gap-1 pt-4 text-sm font-medium text-accent">
        {tool.status === "available" ? "Use tool" : "Learn more"}
        <ArrowRight className="size-4 transition-transform group-hover:translate-x-1" />
      </span>
    </article>
  );
}
