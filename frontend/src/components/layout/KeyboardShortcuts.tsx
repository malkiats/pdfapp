"use client";

import { useRouter } from "next/navigation";
import { useEffect } from "react";

function isTyping(target: EventTarget | null): boolean {
  if (!(target instanceof HTMLElement)) return false;
  return target.isContentEditable || ["INPUT", "TEXTAREA", "SELECT"].includes(target.tagName);
}

/**
 * Site-wide keyboard shortcut (documented on /accessibility):
 * "/" focuses the tool search, or opens the tools list with the search focused.
 */
export function KeyboardShortcuts() {
  const router = useRouter();
  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key !== "/" || event.ctrlKey || event.metaKey || event.altKey || isTyping(event.target)) return;
      event.preventDefault();
      const search = document.querySelector<HTMLInputElement>("[data-site-search]");
      if (search) {
        search.focus();
        search.select();
      } else {
        router.push("/tools#search");
      }
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [router]);
  return null;
}
