import { ShieldCheck } from "lucide-react";
import { ToolSearch } from "@/components/tools/ToolSearch";
import { Container } from "@/components/ui/Container";
import { retentionSentence } from "@/lib/config/retention";
import type { ToolSummary } from "@/types/catalog";

export function Hero({ tools }: { tools: ToolSummary[] }) {
  return (
    <section aria-labelledby="hero-title" className="border-b border-border bg-surface">
      <Container className="py-14 text-center sm:py-20">
        <p className="mx-auto inline-flex items-center gap-2 rounded-full border border-border bg-bg px-3 py-1 text-sm text-muted">
          <ShieldCheck aria-hidden="true" className="size-4 text-success" />
          Privacy-first document tools
        </p>
        <h1 id="hero-title" className="mx-auto mt-6 max-w-3xl text-4xl font-bold tracking-tight sm:text-5xl">
          Your files. Your privacy. Our tools.
        </h1>
        <p className="mx-auto mt-5 max-w-2xl text-lg text-muted">
          Merge, convert, compress and extract text from your documents online. {retentionSentence}
        </p>
        <div className="mx-auto mt-8 max-w-2xl">
          <ToolSearch tools={tools} />
        </div>
        <p className="mt-4 text-sm text-muted">
          {tools.length} tools on the way. No sign-up needed for the free plan.
        </p>
      </Container>
    </section>
  );
}
