import { FileWarning } from "lucide-react";
import type { ReactNode } from "react";

export function DraftNotice({ children }: { children: ReactNode }) {
  return (
    <div role="note" className="flex gap-3 rounded-xl border border-warning/40 bg-warning-soft p-4 text-sm text-warning">
      <FileWarning aria-hidden="true" className="mt-0.5 size-5 shrink-0" />
      <div>{children}</div>
    </div>
  );
}
