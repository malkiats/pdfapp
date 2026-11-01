import type { BadgeVariant } from "@/components/ui/StatusBadge";
import type { Tool } from "@/types/catalog";
import { ToolCard } from "./ToolCard";

export function ToolGrid({
  tools,
  headingLevel = 3,
  badgeVariant = "default",
}: {
  tools: readonly Tool[];
  headingLevel?: 2 | 3;
  badgeVariant?: BadgeVariant;
}) {
  return (
    <ul className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
      {tools.map((tool) => (
        <li key={tool.slug}>
          <ToolCard tool={tool} headingLevel={headingLevel} badgeVariant={badgeVariant} />
        </li>
      ))}
    </ul>
  );
}
