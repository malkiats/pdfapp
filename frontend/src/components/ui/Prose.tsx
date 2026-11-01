import type { ReactNode } from "react";

/** Simple long-form text styling without a typography plugin. */
export function Prose({ children }: { children: ReactNode }) {
  return (
    <div className="max-w-3xl space-y-4 leading-7 text-fg [&_a]:text-accent [&_a]:underline [&_a]:underline-offset-4 [&_h2]:mt-10 [&_h2]:text-2xl [&_h2]:font-semibold [&_h3]:mt-6 [&_h3]:text-lg [&_h3]:font-semibold [&_li]:ml-5 [&_ol]:list-decimal [&_ol]:space-y-2 [&_p]:text-muted [&_ul]:list-disc [&_ul]:space-y-2 [&_li]:text-muted">
      {children}
    </div>
  );
}
