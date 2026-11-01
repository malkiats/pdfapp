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
    <header className="border-b border-border bg-surface">
      <Container className="py-10 sm:py-14">
        {eyebrow ? <div className="mb-3 text-sm font-medium text-accent">{eyebrow}</div> : null}
        <h1 className="text-3xl font-bold tracking-tight sm:text-4xl">{title}</h1>
        {description ? <div className="mt-4 max-w-3xl text-lg text-muted">{description}</div> : null}
        {children}
      </Container>
    </header>
  );
}
