import { ShieldCheck } from "lucide-react";
import { ToolSearch } from "@/components/tools/ToolSearch";
import { Container } from "@/components/ui/Container";
import { retentionSentence } from "@/lib/config/retention";
import type { ToolSummary } from "@/types/catalog";

export function Hero({ tools }: { tools: ToolSummary[] }) {
  return (
    <section aria-labelledby="hero-title" className="border-b border-border bg-gradient-to-br from-surface via-surface to-accent-soft/10">
      <Container className="py-16 text-center sm:py-24">
        <div className="space-y-8">
          <div>
            <p className="mx-auto inline-flex items-center gap-2 rounded-full border border-accent/30 bg-accent/10 px-4 py-2 text-sm font-medium text-accent">
              <ShieldCheck aria-hidden="true" className="size-4" />
              Privacy-first & Open Source
            </p>
            <h1 id="hero-title" className="mx-auto mt-8 max-w-4xl text-5xl font-bold tracking-tight sm:text-6xl bg-gradient-to-r from-fg to-fg/80 bg-clip-text text-transparent">
              Professional PDF & Document Tools
            </h1>
            <p className="mx-auto mt-6 max-w-2xl text-xl text-muted leading-relaxed">
              All the tools you need to work with documents. Completely free. No accounts. No limits. {retentionSentence}
            </p>
          </div>
          <div className="mx-auto mt-10 max-w-2xl">
            <ToolSearch tools={tools} />
          </div>
          <p className="text-sm text-muted font-medium">
            {tools.length} professional tools • 100% open source • Zero tracking
          </p>
        </div>
      </Container>
    </section>
  );
}
