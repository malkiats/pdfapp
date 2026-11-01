import { siteConfig } from "@/lib/config/site";

/** Visible marker next to example.com contact addresses until real mailboxes exist (launch blocker). */
export function PlaceholderTag() {
  if (!siteConfig.contactIsPlaceholder) return null;
  return (
    <span className="ml-2 inline-flex items-center rounded-full bg-warning-soft px-2 py-0.5 align-middle text-xs font-medium text-warning">
      Placeholder
    </span>
  );
}
