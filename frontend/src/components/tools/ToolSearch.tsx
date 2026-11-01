"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { Search } from "lucide-react";
import { useId, useMemo, useRef, useState, type KeyboardEvent } from "react";
import { searchTools } from "@/lib/search";
import type { ToolSummary } from "@/types/catalog";

interface ToolSearchProps {
  tools: readonly ToolSummary[];
  label?: string;
  placeholder?: string;
  limit?: number;
}

/**
 * Client-side catalog search. Keyboard: type to filter, Enter opens the top
 * result, ArrowDown/ArrowUp move through results, Escape clears and returns to
 * the input. Result count is announced through a polite live region.
 */
export function ToolSearch({
  tools,
  label = "Search tools",
  placeholder = "Search tools, e.g. merge PDF",
  limit = 8,
}: ToolSearchProps) {
  const router = useRouter();
  const [query, setQuery] = useState("");
  const inputRef = useRef<HTMLInputElement>(null);
  const listRef = useRef<HTMLUListElement>(null);
  const inputId = useId();
  const listId = useId();
  const statusId = useId();

  const results = useMemo(() => searchTools(tools, query, limit), [tools, query, limit]);
  const hasQuery = query.trim().length > 0;

  const links = () => Array.from(listRef.current?.querySelectorAll<HTMLAnchorElement>("a[data-result]") ?? []);

  const focusResult = (index: number) => {
    const all = links();
    if (all.length === 0) return;
    const clamped = Math.max(0, Math.min(index, all.length - 1));
    all[clamped]?.focus();
  };

  const onInputKeyDown = (event: KeyboardEvent<HTMLInputElement>) => {
    if (event.key === "ArrowDown") {
      event.preventDefault();
      focusResult(0);
    } else if (event.key === "Escape") {
      setQuery("");
    }
  };

  const onListKeyDown = (event: KeyboardEvent<HTMLUListElement>) => {
    const all = links();
    const index = all.findIndex((a) => a === document.activeElement);
    if (event.key === "ArrowDown") {
      event.preventDefault();
      focusResult(index + 1);
    } else if (event.key === "ArrowUp") {
      event.preventDefault();
      if (index <= 0) inputRef.current?.focus();
      else focusResult(index - 1);
    } else if (event.key === "Escape") {
      event.preventDefault();
      setQuery("");
      inputRef.current?.focus();
    }
  };

  const statusText = !hasQuery
    ? ""
    : results.length === 0
      ? "No tools match your search."
      : `${results.length} ${results.length === 1 ? "tool" : "tools"} found.`;

  return (
    <div className="relative w-full">
      <form
        role="search"
        onSubmit={(event) => {
          event.preventDefault();
          const first = results[0];
          if (first) router.push(`/tools/${first.slug}`);
        }}
      >
        <label htmlFor={inputId} className="sr-only">
          {label}
        </label>
        <div className="relative">
          <Search aria-hidden="true" className="pointer-events-none absolute left-4 top-1/2 size-5 -translate-y-1/2 text-muted" />
          <input
            ref={inputRef}
            id={inputId}
            type="search"
            autoComplete="off"
            spellCheck={false}
            value={query}
            placeholder={placeholder}
            onChange={(event) => setQuery(event.target.value)}
            onKeyDown={onInputKeyDown}
            aria-controls={hasQuery ? listId : undefined}
            aria-describedby={statusId}
            className="h-14 w-full rounded-xl border border-border-strong bg-bg pl-12 pr-4 text-base text-fg shadow-sm placeholder:text-muted focus:border-accent focus:outline-none focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring"
          />
        </div>
      </form>
      <p id={statusId} role="status" aria-live="polite" className="sr-only">
        {statusText}
      </p>
      {hasQuery ? (
        <div className="mt-2 rounded-xl border border-border bg-bg p-2 text-left shadow-lg">
          {results.length > 0 ? (
            <ul id={listId} ref={listRef} aria-label="Search results" onKeyDown={onListKeyDown} className="space-y-1">
              {results.map((tool) => (
                <li key={tool.slug}>
                  <Link
                    data-result=""
                    href={`/tools/${tool.slug}`}
                    className="block rounded-lg px-3 py-2 hover:bg-surface-strong focus:bg-surface-strong"
                  >
                    <span className="flex items-center justify-between gap-2">
                      <span className="font-medium">{tool.title}</span>
                      <span className="text-xs text-muted">{tool.categoryName}</span>
                    </span>
                    <span className="mt-0.5 block text-sm text-muted">{tool.description}</span>
                  </Link>
                </li>
              ))}
            </ul>
          ) : (
            <p className="px-3 py-2 text-sm text-muted">
              No tools match &ldquo;{query.trim()}&rdquo;.{" "}
              <Link href="/tools" className="text-accent underline underline-offset-4">
                Browse all tools
              </Link>
            </p>
          )}
        </div>
      ) : null}
    </div>
  );
}
