import type { ReactNode } from "react";
import { Container } from "./Container";

export function PageHeader({
  eyebrow,
  title,
  description,
  children,
}: {
  eyebrow?: ReactNode;
  title: ReactNode;
  description?: ReactNode;
  children?: ReactNode;
}) {
  return (
    <header className="border-b border-border/50 bg-gradient-to-br from-surface via-surface to-accent-soft/5">
      <Container className="py-12 sm:py-16">
        {eyebrow ? <div className="mb-4 inline-flex items-center rounded-full border border-accent/30 bg-accent/10 px-3 py-1 text-sm font-medium text-accent">{eyebrow}</div> : null}
        <h1 className="text-4xl font-bold tracking-tight sm:text-5xl bg-gradient-to-r from-fg to-fg/80 bg-clip-text text-transparent">{title}</h1>
        {description ? <div className="mt-6 max-w-3xl text-xl text-muted leading-relaxed">{description}</div> : null}
        {children}
      </Container>
    </header>
  );
}
