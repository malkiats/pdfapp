"use client";

import type { PDFDocumentProxy } from "pdfjs-dist";
import { useCallback, useEffect, useRef, useState } from "react";
import { createRenderQueue } from "@/lib/pdf/renderQueue";
import { closePdf, openPdf, PdfOpenError, renderThumbnail, type Thumbnail } from "@/lib/pdf/thumbnails";

/** Thumbnails are drawn at this CSS width (the largest zoom step) and scaled down by CSS. */
export const THUMB_RENDER_WIDTH = 240;
/** Pages rendered at the same time; keeps big documents responsive. */
const RENDER_CONCURRENCY = 2;

export type PdfLoadState =
  | { status: "loading" }
  | { status: "ready"; doc: PDFDocumentProxy; pageCount: number }
  | { status: "error"; reason: "password" | "invalid" };

/** Opens a local PDF with pdf.js; destroys it on change/unmount. */
export function usePdfDocument(file: Blob): PdfLoadState {
  // Tagged with the file it belongs to, so a new file reads as "loading" at once.
  const [tagged, setTagged] = useState<{ file: Blob | null; state: PdfLoadState }>({ file: null, state: { status: "loading" } });
  const setState = useCallback((next: PdfLoadState) => setTagged({ file, state: next }), [file]);
  useEffect(() => {
    let live = true;
    let opened: PDFDocumentProxy | null = null;
    openPdf(file)
      .then((doc) => {
        if (!live) {
          void closePdf(doc);
          return;
        }
        opened = doc;
        setState({ status: "ready", doc, pageCount: doc.numPages });
      })
      .catch((error: unknown) => {
        if (live) setState({ status: "error", reason: error instanceof PdfOpenError ? error.reason : "invalid" });
      });
    return () => {
      live = false;
      if (opened) void closePdf(opened);
    };
  }, [file, setState]);
  return tagged.file === file ? tagged.state : { status: "loading" };
}

/** `null` marks a page whose preview could not be drawn. */
export type ThumbnailMap = ReadonlyMap<number, Thumbnail | null>;

/**
 * Lazily renders thumbnails for pages whose element is near the viewport
 * (IntersectionObserver), at most RENDER_CONCURRENCY at a time. Pages scrolled
 * past before their turn are skipped. Returns the thumbnails and a ref factory
 * for page elements.
 */
export function usePdfThumbnails(doc: PDFDocumentProxy | null) {
  const [thumbs, setThumbs] = useState<Map<number, Thumbnail | null>>(() => new Map());
  const elements = useRef(new Map<Element, number>());
  const observerRef = useRef<IntersectionObserver | null>(null);

  useEffect(() => {
    if (!doc) return;
    let live = true;
    const urls: string[] = [];
    const done = new Set<number>();
    const cancels = new Map<number, () => void>();

    const queue = createRenderQueue<number>(async (page) => {
      // Started (or finished) pages are never queued again.
      done.add(page);
      cancels.delete(page);
      let thumb: Thumbnail | null = null;
      try {
        thumb = await renderThumbnail(doc, page, THUMB_RENDER_WIDTH);
      } catch {
        thumb = null;
      }
      if (!live) {
        if (thumb) URL.revokeObjectURL(thumb.url);
        return;
      }
      if (thumb) urls.push(thumb.url);
      setThumbs((prev) => new Map(prev).set(page, thumb));
    }, RENDER_CONCURRENCY);

    const observer =
      typeof IntersectionObserver === "undefined"
        ? null
        : new IntersectionObserver(
            (entries) => {
              for (const entry of entries) {
                const page = elements.current.get(entry.target);
                if (page === undefined || done.has(page)) continue;
                if (entry.isIntersecting) {
                  if (!cancels.has(page)) cancels.set(page, queue.request(page));
                } else {
                  cancels.get(page)?.();
                  cancels.delete(page);
                }
              }
            },
            { rootMargin: "400px 0px" },
          );
    observerRef.current = observer;
    // Page elements may have mounted before this effect ran.
    for (const el of elements.current.keys()) observer?.observe(el);

    return () => {
      live = false;
      observer?.disconnect();
      observerRef.current = null;
      queue.clear();
      for (const url of urls) URL.revokeObjectURL(url);
    };
  }, [doc]);

  /** Ref callback for the element of page `page` (React 19 ref cleanup). */
  const observe = useCallback((el: Element, page: number) => {
    elements.current.set(el, page);
    observerRef.current?.observe(el);
    return () => {
      elements.current.delete(el);
      observerRef.current?.unobserve(el);
    };
  }, []);

  return { thumbs: thumbs as ThumbnailMap, observe };
}
