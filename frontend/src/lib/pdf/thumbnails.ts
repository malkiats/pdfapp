/**
 * Client-side PDF page thumbnails with pdf.js. Files never leave the browser
 * here: the document is parsed in a Web Worker and each page is drawn to a
 * throwaway canvas, then kept only as a small JPEG object URL.
 */
import "client-only";
import type { PDFDocumentProxy } from "pdfjs-dist";

type PdfJs = typeof import("pdfjs-dist");

let pdfjsPromise: Promise<PdfJs> | null = null;

/** Loads pdf.js on demand and wires its worker once (bundled by Next via `new URL(..., import.meta.url)`). */
export function loadPdfjs(): Promise<PdfJs> {
  pdfjsPromise ??= import("pdfjs-dist").then((pdfjs) => {
    if (!pdfjs.GlobalWorkerOptions.workerPort) {
      pdfjs.GlobalWorkerOptions.workerPort = new Worker(new URL("pdfjs-dist/build/pdf.worker.min.mjs", import.meta.url), {
        type: "module",
      });
    }
    return pdfjs;
  });
  return pdfjsPromise;
}

export class PdfOpenError extends Error {
  readonly reason: "password" | "invalid";
  constructor(reason: "password" | "invalid") {
    super(reason);
    this.name = "PdfOpenError";
    this.reason = reason;
  }
}

/** Releases a document opened with openPdf (the shared worker stays up for the next one). */
export function closePdf(doc: PDFDocumentProxy): Promise<void> {
  return doc.loadingTask.destroy();
}

/** Opens a local PDF. Rejects with PdfOpenError for encrypted or unreadable files. */
export async function openPdf(file: Blob): Promise<PDFDocumentProxy> {
  const pdfjs = await loadPdfjs();
  const data = new Uint8Array(await file.arrayBuffer());
  // No wasm decoders: the CSP has no 'wasm-unsafe-eval'; pdf.js falls back to its JS decoders.
  const task = pdfjs.getDocument({ data, useWasm: false, enableXfa: false });
  try {
    return await task.promise;
  } catch (error) {
    void task.destroy();
    const name = (error as { name?: string } | null)?.name;
    throw new PdfOpenError(name === "PasswordException" ? "password" : "invalid");
  }
}

export interface Thumbnail {
  /** JPEG object URL; revoke it when no longer shown. */
  url: string;
  /** Width / height of the page as displayed (rotation applied). */
  aspect: number;
}

/** Renders page `pageNumber` (1-based) about `cssWidth` CSS pixels wide. */
export async function renderThumbnail(doc: PDFDocumentProxy, pageNumber: number, cssWidth: number): Promise<Thumbnail> {
  const page = await doc.getPage(pageNumber);
  const canvas = document.createElement("canvas");
  try {
    const base = page.getViewport({ scale: 1 });
    const dpr = Math.min(window.devicePixelRatio || 1, 2);
    const viewport = page.getViewport({ scale: (cssWidth * dpr) / base.width });
    canvas.width = Math.max(1, Math.ceil(viewport.width));
    canvas.height = Math.max(1, Math.ceil(viewport.height));
    await page.render({ canvas, viewport }).promise;
    const blob = await new Promise<Blob | null>((resolve) => canvas.toBlob(resolve, "image/jpeg", 0.8));
    if (!blob) throw new Error("thumbnail encoding failed");
    return { url: URL.createObjectURL(blob), aspect: base.width / base.height };
  } finally {
    // Release the bitmap and the page's parsed resources right away.
    canvas.width = 0;
    canvas.height = 0;
    page.cleanup();
  }
}
