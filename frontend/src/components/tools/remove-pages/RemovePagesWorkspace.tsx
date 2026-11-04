"use client";

import { AlertCircle, CheckCircle2, Download, FileText, Keyboard, Loader2, RefreshCw, RotateCcw, Trash2 } from "lucide-react";
import { memo, useCallback, useEffect, useId, useRef, useState, type KeyboardEvent, type MouseEvent } from "react";
import type { useToolRunner } from "@/hooks/useToolRunner";
import { derivedFilename } from "@/lib/api/uploads";
import { formatBytes } from "@/lib/format";
import { applyPageClick, formatPageRanges, parsePageRanges, toPagesOption } from "@/lib/pageRanges";
import type { Thumbnail } from "@/lib/pdf/thumbnails";
import { overallPercent, ProcessingStatus, UploadProgressBar } from "../ProcessingStatus";
import { usePdfDocument, usePdfThumbnails } from "./usePdfThumbnails";

export interface RemovePagesWorkspaceProps {
  file: File;
  /** Runner for the remove-pages tool (inline or large-file flow). */
  runner: ReturnType<typeof useToolRunner>;
  /** Back to the file picker. */
  onChangeFile: () => void;
}

interface Selection {
  pages: ReadonlySet<number>;
  /** Text in the "Pages to remove" field, as typed or as rewritten from the grid. */
  text: string;
  /** Last clicked page, the anchor for Shift ranges. */
  anchor: number | null;
  invalid: string[];
  outOfRange: string[];
}

const EMPTY: Selection = { pages: new Set(), text: "", anchor: null, invalid: [], outOfRange: [] };
const ZOOM = { min: 100, max: 240, step: 20, initial: 140 };
/** One instance per page, so a fixed id is safe and gives the skip link a stable target. */
const INPUT_ID = "remove-pages-input";

const secondaryButton =
  "inline-flex min-h-11 items-center gap-2 rounded-lg border border-border-strong bg-bg px-4 text-sm font-medium hover:bg-surface-strong disabled:cursor-not-allowed disabled:opacity-60";
/** Display (flex/hidden) is set per use: the panel CTA is lg+ only. */
const primaryButton =
  "w-full items-center justify-center gap-2 rounded-lg bg-accent px-4 text-base font-semibold text-accent-fg hover:bg-accent-hover disabled:cursor-not-allowed disabled:opacity-60 aria-disabled:cursor-progress aria-disabled:opacity-80";

/** Number of columns the grid currently lays out (for Up/Down arrows). */
function columnCount(grid: HTMLElement): number {
  const columns = getComputedStyle(grid).gridTemplateColumns.split(" ").filter(Boolean).length;
  return Math.max(1, columns);
}

/**
 * Remove-pages workspace: a lazily rendered thumbnail grid of the local PDF
 * (left) and a sticky control panel (right; below on small screens, with a
 * fixed action bar). Grid clicks and the "Pages to remove" field stay in sync.
 * The grid is one tab stop (roving tabindex): arrows move, Space/Enter toggle,
 * Shift+arrows or Shift+Enter extend a range, Home/End jump.
 */
export function RemovePagesWorkspace({ file, runner, onChangeFile }: RemovePagesWorkspaceProps) {
  const pdf = usePdfDocument(file);
  const doc = pdf.status === "ready" ? pdf.doc : null;
  const total = pdf.status === "ready" ? pdf.pageCount : 0;
  const { thumbs, observe } = usePdfThumbnails(doc);
  const [selection, setSelection] = useState<Selection>(EMPTY);
  const [focusPage, setFocusPage] = useState(1);
  const [zoom, setZoom] = useState(ZOOM.initial);
  const gridRef = useRef<HTMLUListElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const panelCtaRef = useRef<HTMLButtonElement>(null);
  const barCtaRef = useRef<HTMLButtonElement>(null);
  const focusCtaRef = useRef(false);
  const asideRef = useRef<HTMLElement>(null);
  const barDownloadRef = useRef<HTMLButtonElement>(null);
  const hintId = useId();
  const zoomId = useId();
  const { state, busy } = runner;

  const count = selection.pages.size;
  const allSelected = total > 0 && count >= total;
  const finished = state.phase === "succeeded";
  const failed = state.phase === "failed";
  const canRemove = doc !== null && count > 0 && !allSelected && selection.invalid.length === 0;

  const activate = useCallback((page: number, shift: boolean) => {
    setFocusPage(page);
    setSelection((s) => {
      const pages = applyPageClick(s.pages, page, { shift, anchor: s.anchor });
      return { pages, text: formatPageRanges(pages), anchor: page, invalid: [], outOfRange: [] };
    });
  }, []);

  /** Shift+arrow: add the span from the anchor (or the page we came from) to `to`. */
  const extendTo = (from: number, to: number) => {
    setSelection((s) => {
      const anchor = s.anchor ?? from;
      const pages = applyPageClick(s.pages, to, { shift: true, anchor });
      return { pages, text: formatPageRanges(pages), anchor, invalid: [], outOfRange: [] };
    });
  };

  const onGridKeyDown = (event: KeyboardEvent<HTMLUListElement>) => {
    const grid = gridRef.current;
    const current = Number((event.target as HTMLElement).closest<HTMLElement>("[data-page]")?.dataset.page);
    if (!grid || !Number.isInteger(current) || total === 0) return;

    if (event.shiftKey && (event.key === "Enter" || event.key === " ")) {
      event.preventDefault();
      activate(current, true);
      return;
    }
    const cols = columnCount(grid);
    const moves: Record<string, number> = {
      ArrowRight: current + 1,
      ArrowLeft: current - 1,
      ArrowDown: current + cols,
      ArrowUp: current - cols,
      Home: 1,
      End: total,
    };
    if (!(event.key in moves)) return;
    event.preventDefault();
    const target = Math.min(total, Math.max(1, moves[event.key]!));
    if (event.shiftKey && event.key.startsWith("Arrow")) extendTo(current, target);
    setFocusPage(target);
    grid.querySelector<HTMLButtonElement>(`[data-page="${target}"]`)?.focus();
  };

  const onInput = (value: string) => {
    const parsed = parsePageRanges(value, total);
    setSelection((s) => ({
      pages: new Set(parsed.pages),
      text: value,
      anchor: s.anchor,
      invalid: parsed.invalid,
      outOfRange: parsed.outOfRange,
    }));
  };

  const onBlur = () => {
    setSelection((s) =>
      s.invalid.length === 0 && s.outOfRange.length === 0 ? { ...s, text: formatPageRanges(s.pages) } : s,
    );
  };

  const clear = () => setSelection(EMPTY);

  const focusInput = () => {
    const el = inputRef.current;
    if (!el) return;
    el.focus({ preventScroll: true });
    el.scrollIntoView?.({ block: "center", behavior: "smooth" });
  };

  const remove = () => {
    // aria-disabled while busy keeps focus on the button; ignore the click.
    if (!canRemove || busy) return;
    void runner.run({
      files: [file],
      options: { pages: toPagesOption(selection.pages) },
      downloadName: derivedFilename(file.name, "-removed", "pdf"),
    });
  };

  /** Cancel, then put focus back on the visible Remove control (the Cancel button disappears). */
  const cancel = () => {
    focusCtaRef.current = true;
    runner.cancel();
  };
  useEffect(() => {
    if (!focusCtaRef.current || busy) return;
    focusCtaRef.current = false;
    const visible = [barCtaRef.current, panelCtaRef.current].find((el) => el && el.offsetParent !== null);
    (visible ?? panelCtaRef.current)?.focus();
  }, [busy]);

  // On success, focus the visible Download button (the bar's below lg, the panel's at lg+).
  const focusedSuccessRef = useRef(false);
  useEffect(() => {
    if (!finished) {
      focusedSuccessRef.current = false;
      return;
    }
    if (focusedSuccessRef.current || doc === null) return; // once per success, after the controls exist
    focusedSuccessRef.current = true;
    const panel = asideRef.current?.querySelector<HTMLButtonElement>('[data-action="download"]') ?? null;
    const visible = [barDownloadRef.current, panel].find((el) => el && el.offsetParent !== null);
    (visible ?? barDownloadRef.current ?? panel)?.focus();
  }, [finished, doc]);

  const removeMore = () => {
    runner.reset();
    setSelection(EMPTY);
  };

  if (pdf.status === "error") {
    return (
      <div role="alert" className="max-w-3xl rounded-2xl border border-danger/40 bg-danger-soft p-5">
        <p className="flex items-center gap-2 font-semibold">
          <AlertCircle aria-hidden="true" className="size-5 text-danger" />
          {pdf.reason === "password" ? "This PDF is password protected" : "This file could not be opened"}
        </p>
        <p className="mt-1 text-sm">
          {pdf.reason === "password"
            ? "Remove the password with Unlock PDF first, then try again."
            : "It may be damaged or not a PDF. Try another file."}
        </p>
        <button type="button" onClick={onChangeFile} className={`${secondaryButton} mt-3`}>
          <RefreshCw aria-hidden="true" className="size-4" />
          Choose another file
        </button>
      </div>
    );
  }

  const hint =
    selection.invalid.length > 0
      ? `Not understood: ${selection.invalid.join(", ")}. Use page numbers and ranges such as 1, 5-8.`
      : selection.outOfRange.length > 0
        ? `Ignored, the document has ${total} ${total === 1 ? "page" : "pages"}: ${selection.outOfRange.join(", ")}.`
        : null;

  const summary =
    count === 0 ? (
      <span className="text-muted">No pages selected.</span>
    ) : allSelected ? (
      <span className="font-medium text-danger">You can&apos;t remove every page.</span>
    ) : (
      <span>
        <span className="font-semibold">{count}</span> {count === 1 ? "page" : "pages"} selected, {total - count} will
        remain.
      </span>
    );

  const ctaLabel =
    state.phase === "uploading" ? "Uploading…" : state.phase === "processing" ? "Removing…" : failed ? "Try again" : "Remove pages";

  return (
    <div className="grid gap-6 pb-32 lg:grid-cols-[minmax(0,1fr)_20rem] lg:items-start lg:pb-0">
      <div className="min-w-0 rounded-2xl border border-border bg-surface p-4">
        <div className="flex flex-wrap items-center gap-3 border-b border-border pb-3">
          <FileText aria-hidden="true" className="size-5 shrink-0 text-muted" />
          <span className="min-w-0 flex-1 basis-40 truncate text-sm font-medium" title={file.name}>
            {file.name}
          </span>
          <span className="shrink-0 text-xs text-muted">{formatBytes(file.size)}</span>
          <div className="hidden items-center gap-2 sm:flex">
            <label htmlFor={zoomId} className="text-xs text-muted">
              Thumbnail size
            </label>
            <input
              id={zoomId}
              type="range"
              min={ZOOM.min}
              max={ZOOM.max}
              step={ZOOM.step}
              value={zoom}
              onChange={(e) => setZoom(Number(e.target.value))}
              className="w-24 accent-accent"
            />
          </div>
          <button type="button" onClick={onChangeFile} disabled={busy} className={secondaryButton}>
            <RefreshCw aria-hidden="true" className="size-4" />
            Change file
          </button>
        </div>

        {doc === null ? (
          <p className="flex items-center gap-2 py-10 text-sm text-muted" role="status">
            <Loader2 aria-hidden="true" className="size-4 animate-spin" />
            Reading pages…
          </p>
        ) : (
          <>
            <a
              href={`#${INPUT_ID}`}
              onClick={(e) => {
                e.preventDefault();
                focusInput();
              }}
              className="sr-only rounded-lg bg-accent px-3 py-2 text-sm font-medium text-accent-fg focus:not-sr-only focus:mt-3 focus:inline-block"
            >
              Skip to Pages to remove
            </a>
            <ul
              ref={gridRef}
              aria-label="Pages"
              aria-describedby={`${hintId}-grid`}
              onKeyDown={onGridKeyDown}
              className="mt-4 grid select-none gap-3"
              style={{ gridTemplateColumns: `repeat(auto-fill, minmax(min(${zoom}px, 100%), 1fr))` }}
            >
              {Array.from({ length: total }, (_, i) => i + 1).map((page) => (
                <li key={page}>
                  <PageThumb
                    page={page}
                    thumb={thumbs.get(page)}
                    selected={selection.pages.has(page)}
                    tabbable={page === Math.min(focusPage, total)}
                    disabled={busy || finished}
                    observe={observe}
                    onActivate={activate}
                  />
                </li>
              ))}
            </ul>
            <p id={`${hintId}-grid`} className="sr-only">
              Use the arrow keys to move between pages, Space or Enter to mark a page, and Shift with arrows or Enter to
              mark a range.
            </p>
          </>
        )}
      </div>

      <aside
        ref={asideRef}
        aria-label="Remove pages options"
        className="space-y-4 rounded-2xl border border-border bg-surface p-5 lg:sticky lg:top-24"
      >
        <div>
          <h2 className="text-lg font-semibold">Remove pages</h2>
          <p className="mt-1 text-sm text-muted">
            Click the pages you want to remove. Hold Shift to select a range. Or type the page numbers below.
          </p>
        </div>

        <p className="text-sm">
          Total pages: <span className="font-semibold">{doc ? total : "…"}</span>
        </p>

        <div>
          <label htmlFor={INPUT_ID} className="text-sm font-medium">
            Pages to remove
          </label>
          <input
            ref={inputRef}
            id={INPUT_ID}
            type="text"
            inputMode="text"
            autoComplete="off"
            spellCheck={false}
            placeholder="e.g. 1, 5-8"
            value={selection.text}
            disabled={doc === null || busy || finished}
            onChange={(e) => onInput(e.target.value)}
            onBlur={onBlur}
            aria-describedby={hintId}
            aria-invalid={selection.invalid.length > 0 || undefined}
            className="mt-1 h-11 w-full scroll-mb-40 rounded-lg border border-border-strong bg-bg px-3 disabled:cursor-not-allowed disabled:bg-surface-strong disabled:text-muted"
          />
          <p id={hintId} aria-live="polite" className={`mt-1 text-xs ${hint ? "text-danger" : "text-muted"}`}>
            {hint ?? "Separate pages with commas. Ranges like 5-8 or 8-5 both work."}
          </p>
        </div>

        <p aria-live="polite" className="text-sm">
          {summary}
        </p>

        {finished ? null : (
          <div className="space-y-2">
            <button
              type="button"
              ref={panelCtaRef}
              onClick={remove}
              disabled={!canRemove}
              aria-disabled={busy || undefined}
              className={`${primaryButton} hidden min-h-12 lg:inline-flex`}
            >
              <Trash2 aria-hidden="true" className="size-5" />
              {ctaLabel}
            </button>
            <button
              type="button"
              onClick={clear}
              disabled={count === 0 || busy}
              className="min-h-11 text-sm font-medium text-accent hover:underline disabled:cursor-not-allowed disabled:text-muted disabled:no-underline"
            >
              Clear selection
            </button>
          </div>
        )}

        {/* While busy, small screens show progress/Cancel in the bar only (one progressbar). */}
        <div className={busy ? "hidden lg:block" : undefined}>
          <ProcessingStatus
            state={state}
            onDownload={runner.result ? runner.download : undefined}
            onRetry={runner.reset}
            retryLabel="Dismiss"
            onCancel={runner.cancellable ? cancel : undefined}
            focusOnError
          />
        </div>

        {finished ? (
          <div className="flex flex-wrap gap-2">
            <button type="button" onClick={removeMore} className={secondaryButton}>
              <Trash2 aria-hidden="true" className="size-4" />
              Remove more pages
            </button>
            <button type="button" onClick={onChangeFile} className={secondaryButton}>
              <RotateCcw aria-hidden="true" className="size-4" />
              Start over
            </button>
          </div>
        ) : null}
      </aside>

      {/* Small screens: the panel is far below a long grid, so keep the action in reach. */}
      {doc !== null ? (
        <div
          data-testid="mobile-action-bar"
          className="fixed inset-x-0 bottom-0 z-30 border-t border-border bg-surface px-4 pt-3 pb-[max(0.75rem,env(safe-area-inset-bottom))] shadow-[0_-4px_12px_rgb(0_0_0/0.08)] lg:hidden"
        >
          <div className="mx-auto flex max-w-3xl flex-col gap-2">
            {finished ? (
              <>
                <p className="flex items-center gap-2 text-sm font-medium">
                  <CheckCircle2 aria-hidden="true" className="size-4 text-success" />
                  {state.phase === "succeeded" && state.expired ? "Result expired" : "Result ready"}
                </p>
                {runner.result && !(state.phase === "succeeded" && state.expired) ? (
                  <button ref={barDownloadRef} type="button" onClick={runner.download} className={`${primaryButton} inline-flex min-h-12`}>
                    <Download aria-hidden="true" className="size-5" />
                    Download result
                  </button>
                ) : null}
                <div className="flex gap-2">
                  <button type="button" onClick={removeMore} className={`${secondaryButton} flex-1 justify-center`}>
                    Remove more pages
                  </button>
                  <button type="button" onClick={onChangeFile} className={`${secondaryButton} flex-1 justify-center`}>
                    Start over
                  </button>
                </div>
              </>
            ) : busy ? (
              // While a request runs, the bar carries its progress and the Cancel action.
              <div className="flex items-center gap-3">
                <div className="min-w-0 flex-1">
                  <p className="text-sm font-medium">
                    {state.phase === "uploading" ? `Uploading ${overallPercent(state.progress)}%` : "Processing…"}
                  </p>
                  {state.phase === "uploading" ? (
                    <UploadProgressBar percent={overallPercent(state.progress)} className="mt-1.5" />
                  ) : (
                    <Loader2 aria-hidden="true" className="mt-1 size-4 animate-spin text-accent" />
                  )}
                </div>
                {runner.cancellable ? (
                  <button type="button" onClick={cancel} className={`${secondaryButton} shrink-0`}>
                    Cancel
                  </button>
                ) : null}
              </div>
            ) : (
              <>
                <div className="flex items-center justify-between gap-3 text-sm">
                  <span aria-hidden="true">
                    {allSelected ? (
                      <span className="font-medium text-danger">You can&apos;t remove every page</span>
                    ) : selection.invalid.length > 0 ? (
                      <span className="font-medium text-danger">Check the page list</span>
                    ) : (
                      <>
                        <span className="font-semibold">{count}</span> selected · {total - count} remain
                      </>
                    )}
                  </span>
                  <button
                    type="button"
                    onClick={focusInput}
                    className="inline-flex min-h-11 items-center gap-1.5 rounded-lg px-2 font-medium text-accent hover:underline"
                  >
                    <Keyboard aria-hidden="true" className="size-4" />
                    Type pages
                  </button>
                </div>
                <button
                  ref={barCtaRef}
                  type="button"
                  onClick={remove}
                  disabled={!canRemove}
                  className={`${primaryButton} inline-flex min-h-12`}
                >
                  <Trash2 aria-hidden="true" className="size-5" />
                  {ctaLabel}
                </button>
              </>
            )}
          </div>
        </div>
      ) : null}
    </div>
  );
}

interface PageThumbProps {
  page: number;
  thumb: Thumbnail | null | undefined;
  selected: boolean;
  /** The grid's single tab stop. */
  tabbable: boolean;
  disabled: boolean;
  observe: (el: Element, page: number) => () => void;
  onActivate: (page: number, shift: boolean) => void;
}

/** One page: a toggle button (aria-pressed). Click toggles, Shift+click selects a range. */
const PageThumb = memo(function PageThumb({ page, thumb, selected, tabbable, disabled, observe, onActivate }: PageThumbProps) {
  const ref = useCallback((el: HTMLButtonElement | null) => (el ? observe(el, page) : undefined), [observe, page]);
  const onClick = (event: MouseEvent<HTMLButtonElement>) => onActivate(page, event.shiftKey);

  return (
    <button
      ref={ref}
      type="button"
      data-page={page}
      tabIndex={tabbable ? 0 : -1}
      aria-pressed={selected}
      disabled={disabled}
      onClick={onClick}
      className={[
        "group flex w-full flex-col items-center gap-2 rounded-xl border-2 p-2 transition-colors disabled:cursor-not-allowed",
        selected ? "border-danger bg-danger-soft" : "border-transparent hover:border-border-strong hover:bg-surface-strong",
      ].join(" ")}
    >
      {/* Fixed-height box so labels line up; pages keep their own shape inside. */}
      <span className="relative flex aspect-[1/1.414] w-full items-center justify-center">
        {thumb ? (
          // Local blob: URL drawn by pdf.js; next/image does not apply.
          // eslint-disable-next-line @next/next/no-img-element
          <img
            src={thumb.url}
            alt=""
            draggable={false}
            className={`max-h-full max-w-full rounded-sm border border-border bg-white object-contain shadow-sm transition-opacity ${
              selected ? "opacity-40" : ""
            }`}
          />
        ) : thumb === null ? (
          <span className="flex size-full items-center justify-center rounded-sm border border-border bg-white p-2 text-center text-xs text-slate-600">
            Preview unavailable
          </span>
        ) : (
          <span aria-hidden="true" className="block size-full animate-pulse rounded-sm bg-slate-100" />
        )}
        {selected ? (
          <>
            <span aria-hidden="true" className="absolute inset-0 rounded-sm bg-danger/15" />
            <span
              aria-hidden="true"
              className="absolute right-1.5 top-1.5 inline-flex size-7 items-center justify-center rounded-full bg-danger text-bg shadow ring-2 ring-white"
            >
              <Trash2 className="size-4" />
            </span>
          </>
        ) : null}
      </span>
      <span className={`text-xs font-medium ${selected ? "text-danger" : ""}`}>Page {page}</span>
    </button>
  );
});
