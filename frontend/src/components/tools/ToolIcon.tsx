import { createElement } from "react";
import { resolveIcon } from "@/lib/icons";

/** Renders a catalog icon by name. Icons come from a static map, so no component is created at render time. */
export function ToolIcon({ name, className = "size-5" }: { name: string; className?: string }) {
  return createElement(resolveIcon(name), { "aria-hidden": true, className });
}
