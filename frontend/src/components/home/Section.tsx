import type { ReactNode } from "react";
import { Container } from "@/components/ui/Container";

export function Section({
  id,
  title,
  description,
  children,
  muted = false,
  action,
}: {
  id: string;
  title: string;
  description?: ReactNode;
  children: ReactNode;
  muted?: boolean;
  action?: ReactNode;
}) {
  return (
    <section aria-labelledby={`${id}-title`} className={muted ? "bg-surface/50 backdrop-blur-sm" : "bg-gradient-to-b from-transparent to-accent-soft/5"}>
      <Container className="py-16 sm:py-20">
        <div className="mb-12 flex flex-wrap items-end justify-between gap-6">
          <div className="max-w-3xl">
            <h2 id={`${id}-title`} className="text-3xl font-bold tracking-tight sm:text-4xl bg-gradient-to-r from-fg to-fg/80 bg-clip-text text-transparent">
              {title}
            </h2>
            {description ? <p className="mt-3 text-lg text-muted leading-relaxed">{description}</p> : null}
          </div>
          {action ? <div className="shrink-0">{action}</div> : null}
        </div>
        <div className="mt-8">
          {children}
        </div>
      </Container>
    </section>
  );
}
