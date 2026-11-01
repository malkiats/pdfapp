import { ChevronDown } from "lucide-react";
import type { ToolFaqItem } from "@/types/catalog";

/**
 * FAQ accordion built on native <details>/<summary>: keyboard accessible and
 * works without JavaScript. Pair with faqJsonLd() for FAQPage structured data.
 */
export function Faq({ items, headingLevel = 3 }: { items: readonly ToolFaqItem[]; headingLevel?: 2 | 3 }) {
  const Heading = headingLevel === 2 ? "h2" : "h3";
  return (
    <div className="divide-y divide-border rounded-xl border border-border bg-bg">
      {items.map((item) => (
        <details key={item.question} className="group px-4 sm:px-5">
          <summary className="flex list-none items-center justify-between gap-4 py-4 text-left font-medium">
            <Heading className="text-base font-medium">{item.question}</Heading>
            <ChevronDown
              aria-hidden="true"
              className="size-5 shrink-0 text-muted transition-transform group-open:rotate-180"
            />
          </summary>
          <p className="pb-4 text-muted">{item.answer}</p>
        </details>
      ))}
    </div>
  );
}
