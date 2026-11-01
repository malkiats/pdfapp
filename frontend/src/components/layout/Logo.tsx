import Link from "next/link";
import { siteConfig } from "@/lib/config/site";

/** Text wordmark. The name comes from siteConfig.name (placeholder brand). */
export function Logo() {
  return (
    <Link href="/" className="inline-flex items-center gap-2 rounded-md text-lg font-bold tracking-tight">
      <span
        aria-hidden="true"
        className="inline-flex size-8 items-center justify-center rounded-lg bg-accent text-sm font-bold text-accent-fg"
      >
        {siteConfig.name.charAt(0)}
      </span>
      <span>{siteConfig.name}</span>
      <span className="sr-only">home</span>
    </Link>
  );
}
