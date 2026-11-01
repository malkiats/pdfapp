import Link from "next/link";
import { ChevronRight } from "lucide-react";

export interface Crumb {
  name: string;
  path: string;
}

export function Breadcrumbs({ items }: { items: Crumb[] }) {
  return (
    <nav aria-label="Breadcrumb" className="mb-4 text-sm text-muted">
      <ol className="flex flex-wrap items-center gap-1">
        {items.map((item, index) => {
          const last = index === items.length - 1;
          return (
            <li key={item.path} className="flex items-center gap-1">
              {last ? (
                <span aria-current="page" className="inline-flex min-h-11 items-center text-fg sm:min-h-0">
                  {item.name}
                </span>
              ) : (
                <>
                  <Link href={item.path} className="inline-flex min-h-11 items-center underline-offset-4 hover:text-fg hover:underline sm:min-h-0">
                    {item.name}
                  </Link>
                  <ChevronRight aria-hidden="true" className="size-4" />
                </>
              )}
            </li>
          );
        })}
      </ol>
    </nav>
  );
}
