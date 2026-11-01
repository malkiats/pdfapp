import type { ToolStatus } from "@/types/catalog";

export type BadgeVariant = "default" | "subtle";

/** Tool status pill. `subtle` is a smaller, muted version for dense grids such as popular tools. */
export function StatusBadge({
  status,
  variant = "default",
  className = "",
}: {
  status: ToolStatus | string;
  variant?: BadgeVariant;
  className?: string;
}) {
  const available = status === "available";
  const label = available ? "Available" : "Coming soon";
  const tone =
    variant === "subtle"
      ? "bg-surface-strong px-1.5 py-0.5 text-[11px] text-muted"
      : available
        ? "bg-success-soft px-2 py-0.5 text-xs text-success"
        : "bg-warning-soft px-2 py-0.5 text-xs text-warning";
  return <span className={`inline-flex shrink-0 items-center rounded-full font-medium ${tone} ${className}`}>{label}</span>;
}
