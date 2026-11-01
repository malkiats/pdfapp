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
    <section aria-labelledby={`${id}-title`} className={muted ? "bg-surface" : undefined}>
      <Container className="py-14 sm:py-16">
        <div className="mb-8 flex flex-wrap items-end justify-between gap-4">
          <div className="max-w-2xl">
            <h2 id={`${id}-title`} className="text-2xl font-bold tracking-tight sm:text-3xl">
              {title}
            </h2>
            {description ? <p className="mt-2 text-muted">{description}</p> : null}
          </div>
          {action}
        </div>
        {children}
      </Container>
    </section>
  );
}
