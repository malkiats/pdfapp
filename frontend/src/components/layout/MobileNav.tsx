"use client";

import Link from "next/link";
import { Menu, X } from "lucide-react";
import { useId, useRef } from "react";
import { mainNav } from "@/lib/config/site";
import type { MenuCategory } from "./nav-types";
import { ThemeToggle } from "./ThemeToggle";

/**
 * Mobile navigation drawer built on the native modal <dialog>: it traps focus,
 * closes on Escape, makes the page inert and restores focus to the opener.
 */
export function MobileNav({ categories }: { categories: MenuCategory[] }) {
  const dialogRef = useRef<HTMLDialogElement>(null);
  const titleId = useId();

  const open = () => dialogRef.current?.showModal();
  const close = () => dialogRef.current?.close();

  return (
    <>
      <button
        type="button"
        onClick={open}
        aria-haspopup="dialog"
        className="inline-flex size-11 items-center justify-center rounded-lg text-fg hover:bg-surface-strong lg:hidden"
      >
        <Menu aria-hidden="true" className="size-6" />
        <span className="sr-only">Open menu</span>
      </button>
      <dialog
        ref={dialogRef}
        aria-labelledby={titleId}
        onClick={(event) => {
          // Clicking the backdrop (the dialog element itself) closes the drawer.
          if (event.target === event.currentTarget) close();
        }}
        className="m-0 ml-auto h-dvh max-h-dvh w-[min(22rem,100vw)] max-w-none overflow-y-auto border-l border-border bg-bg p-0 text-fg"
      >
        <div className="flex items-center justify-between border-b border-border px-4 py-3">
          <h2 id={titleId} className="text-base font-semibold">
            Menu
          </h2>
          <div className="flex items-center gap-1">
            <ThemeToggle />
            <button
              type="button"
              autoFocus
              onClick={close}
              className="inline-flex size-11 items-center justify-center rounded-lg hover:bg-surface-strong"
            >
              <X aria-hidden="true" className="size-6" />
              <span className="sr-only">Close menu</span>
            </button>
          </div>
        </div>
        <nav aria-label="Mobile" className="px-4 py-4">
          <ul className="space-y-1">
            <li>
              <Link href="/tools" onClick={close} className="flex min-h-11 items-center rounded-lg px-3 font-medium hover:bg-surface-strong">
                All tools
              </Link>
            </li>
            {mainNav.map((item) => (
              <li key={item.href}>
                <Link
                  href={item.href}
                  onClick={close}
                  className="flex min-h-11 items-center rounded-lg px-3 font-medium hover:bg-surface-strong"
                >
                  {item.label}
                </Link>
              </li>
            ))}
          </ul>
          <p className="mt-6 px-3 text-xs font-semibold uppercase tracking-wide text-muted">Tool categories</p>
          <ul className="mt-2 space-y-1">
            {categories.map((category) => (
              <li key={category.slug}>
                <Link
                  href={category.href}
                  onClick={close}
                  className="flex min-h-11 items-center rounded-lg px-3 hover:bg-surface-strong"
                >
                  {category.name}
                </Link>
              </li>
            ))}
          </ul>
        </nav>
      </dialog>
    </>
  );
}
