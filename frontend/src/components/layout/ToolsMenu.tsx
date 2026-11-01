"use client";

import Link from "next/link";
import { ChevronDown } from "lucide-react";
import { useCallback, useEffect, useId, useRef, useState } from "react";
import type { MenuCategory } from "./nav-types";

const MAX_TOOLS_PER_CATEGORY = 6;

/**
 * Desktop "Tools" mega-menu: a disclosure button controlling a panel of
 * category columns. Escape closes and returns focus to the button; clicking
 * outside or following a link closes it.
 */
export function ToolsMenu({ categories }: { categories: MenuCategory[] }) {
  const [open, setOpen] = useState(false);
  const panelId = useId();
  const buttonRef = useRef<HTMLButtonElement>(null);
  const rootRef = useRef<HTMLDivElement>(null);
  // Set while a pointer press inside the menu is in progress, so a click on
  // non-focusable panel padding (which blurs to <body>) does not close it.
  const pressingInside = useRef(false);

  const close = useCallback((restoreFocus: boolean) => {
    setOpen(false);
    if (restoreFocus) buttonRef.current?.focus();
  }, []);

  useEffect(() => {
    if (!open) return undefined;
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") close(true);
    };
    const onOutside = (event: Event) => {
      if (rootRef.current && !rootRef.current.contains(event.target as Node)) close(false);
    };
    document.addEventListener("keydown", onKey);
    // pointerdown covers mouse and pen; touchstart covers touch browsers that do not
    // dispatch pointer events for taps on non-interactive content.
    document.addEventListener("pointerdown", onOutside);
    document.addEventListener("touchstart", onOutside, { passive: true });
    return () => {
      document.removeEventListener("keydown", onKey);
      document.removeEventListener("pointerdown", onOutside);
      document.removeEventListener("touchstart", onOutside);
    };
  }, [open, close]);

  return (
    <div
      ref={rootRef}
      className="relative"
      onPointerDown={() => {
        pressingInside.current = true;
      }}
      onPointerUp={() => {
        pressingInside.current = false;
      }}
      onBlur={(event) => {
        if (pressingInside.current) return;
        // Close when keyboard focus leaves the menu entirely (e.g. Tab or Shift+Tab out).
        const next = event.relatedTarget as Node | null;
        if (open && (!next || !event.currentTarget.contains(next))) close(false);
      }}
    >
      <button
        ref={buttonRef}
        type="button"
        aria-expanded={open}
        aria-controls={panelId}
        onClick={() => setOpen((v) => !v)}
        className="inline-flex items-center gap-1 rounded-lg px-3 py-2 text-sm font-medium text-fg hover:bg-surface-strong"
      >
        Tools
        <ChevronDown aria-hidden="true" className={`size-4 transition-transform ${open ? "rotate-180" : ""}`} />
      </button>
      <div
        id={panelId}
        hidden={!open}
        className="fixed inset-x-0 top-16 z-40 border-b border-border-strong bg-bg shadow-2xl shadow-black/15 dark:shadow-black/60"
      >
        <div className="mx-auto max-h-[calc(100vh-5rem)] max-w-6xl overflow-y-auto px-4 py-6 sm:px-6 lg:px-8">
          <div className="grid grid-cols-3 gap-x-8 gap-y-6 xl:grid-cols-5">
            {categories.map((category) => (
              <section key={category.slug} aria-labelledby={`${panelId}-${category.slug}`}>
                <p id={`${panelId}-${category.slug}`} className="text-sm font-semibold">
                  <Link
                    href={category.href}
                    onClick={() => close(false)}
                    className="hover:text-accent hover:underline hover:underline-offset-4"
                  >
                    {category.name}
                  </Link>
                </p>
                <ul className="mt-2 space-y-1">
                  {category.tools.slice(0, MAX_TOOLS_PER_CATEGORY).map((tool) => (
                    <li key={tool.slug}>
                      <Link
                        href={tool.href}
                        onClick={() => close(false)}
                        className="block rounded py-0.5 text-sm text-muted hover:text-fg"
                      >
                        {tool.title}
                      </Link>
                    </li>
                  ))}
                  {category.tools.length > MAX_TOOLS_PER_CATEGORY ? (
                    <li>
                      <Link
                        href={category.href}
                        onClick={() => close(false)}
                        className="block py-0.5 text-sm font-medium text-accent hover:underline"
                      >
                        All {category.tools.length} tools
                      </Link>
                    </li>
                  ) : null}
                </ul>
              </section>
            ))}
          </div>
          <div className="mt-6 border-t border-border pt-4">
            <Link
              href="/tools"
              onClick={() => close(false)}
              className="text-sm font-medium text-accent hover:underline"
            >
              Browse all tools
            </Link>
          </div>
        </div>
      </div>
    </div>
  );
}
