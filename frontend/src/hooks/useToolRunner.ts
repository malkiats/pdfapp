"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import type { ProcessingState } from "@/components/tools/ProcessingStatus";
import {
  deleteUpload,
  FALLBACK_LIMITS,
  fetchLimits,
  needsLargeFlow,
  runInline,
  runLargeFlow,
  ToolRunError,
  triggerDownload,
  type ApiLimits,
  type ToolRequestInput,
} from "@/lib/api/uploads";

/**
 * How long a large-file result stays downloadable before the client deletes it.
 * Inputs are already deleted by the server after processing; the server sweep
 * is the backstop for anything the client could not delete.
 */
export const DOWNLOAD_GRACE_MS = 300_000;

export interface ToolRunResult {
  /** Object URL (inline flow) or presigned download URL (large-file flow). Never logged. */
  url: string;
  filename: string;
  /** Present for inline text results, which are also shown on the page. */
  text?: string;
  remote: boolean;
}

/**
 * Server limits from GET /api/v1/tools. `loaded` turns true once they arrive or
 * the request fails (then the inline-only fallback applies), so callers can
 * defer size checks instead of rejecting files against the fallback.
 */
export function useApiLimits(): { limits: ApiLimits; loaded: boolean } {
  const [value, setValue] = useState<{ limits: ApiLimits; loaded: boolean }>({ limits: FALLBACK_LIMITS, loaded: false });
  useEffect(() => {
    let live = true;
    void fetchLimits().then((limits) => {
      if (live) setValue({ limits: limits ?? FALLBACK_LIMITS, loaded: true });
    });
    return () => {
      live = false;
    };
  }, []);
  return value;
}

export type RunInput = Omit<ToolRequestInput, "slug" | "signal" | "baseUrl"> & {
  /** Local filename for inline results (the large-file flow keeps the server's name). */
  downloadName?: string;
};

/**
 * Runs a tool through the inline or the large-file flow (chosen by size and
 * server limits), tracks the UI state, and cleans up stored uploads on cancel,
 * error, unmount (route change) and page hide. One run at a time.
 */
export function useToolRunner(slug: string, limits: ApiLimits) {
  const [state, setState] = useState<ProcessingState>({ phase: "idle" });
  const [result, setResult] = useState<ToolRunResult | null>(null);
  const [cancellable, setCancellable] = useState(false);
  /** The controller of the run in flight; null when idle (also the double-submit guard). */
  const abortRef = useRef<AbortController | null>(null);
  const uploadIdRef = useRef<string | null>(null);
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  /** Deletes the current stored upload, if any (deleteUpload is once-per-id and keepalive). */
  const releaseUpload = useCallback((unloading = false) => {
    if (timerRef.current) clearTimeout(timerRef.current);
    timerRef.current = null;
    const id = uploadIdRef.current;
    uploadIdRef.current = null;
    if (id) void deleteUpload(id, { unloading });
  }, []);

  const abortRun = useCallback(() => {
    abortRef.current?.abort();
    abortRef.current = null;
  }, []);

  // Leaving the page or the route while a job (or an undeleted result) exists.
  useEffect(() => {
    const onPageHide = () => {
      abortRun();
      releaseUpload(true);
    };
    // Back/forward cache restore: the run was aborted and the upload deleted on hide.
    const onPageShow = (event: PageTransitionEvent) => {
      if (!event.persisted) return;
      setCancellable(false);
      setResult((r) => (r?.remote ? null : r));
      setState((s) =>
        s.phase === "uploading" || s.phase === "processing"
          ? { phase: "idle" }
          : s.phase === "succeeded" && !s.expired && uploadIdRef.current === null
            ? { ...s, expired: true }
            : s,
      );
    };
    window.addEventListener("pagehide", onPageHide);
    window.addEventListener("pageshow", onPageShow);
    return () => {
      window.removeEventListener("pagehide", onPageHide);
      window.removeEventListener("pageshow", onPageShow);
      abortRun();
      releaseUpload();
    };
  }, [abortRun, releaseUpload]);

  // Free the object URL of a previous inline result.
  useEffect(
    () => () => {
      if (result && !result.remote) URL.revokeObjectURL(result.url);
    },
    [result],
  );

  const run = useCallback(
    async (input: RunInput) => {
      if (abortRef.current) return; // a run is already in flight
      const controller = new AbortController();
      abortRef.current = controller;
      const { signal } = controller;
      releaseUpload();
      setResult(null);

      const { downloadName, ...request } = input;
      const total = request.files.reduce((sum, f) => sum + f.size, 0);
      const large = request.files.length > 0 && needsLargeFlow(total, limits);
      setCancellable(large);
      let myId: string | null = null;

      try {
        if (large) {
          setState({ phase: "uploading", progress: request.files.map(() => 0) });
          const out = await runLargeFlow({
            ...request,
            slug,
            signal,
            onUploadCreated: (id) => {
              myId = id;
              if (!signal.aborted) uploadIdRef.current = id;
            },
            onProgress: (progress) => {
              if (!signal.aborted) setState({ phase: "uploading", progress });
            },
            onStage: (stage) => {
              if (stage === "processing" && !signal.aborted) setState({ phase: "processing" });
            },
          });
          if (signal.aborted) throw new ToolRunError("cancelled");
          const next: ToolRunResult = { url: out.download_url, filename: out.filename, remote: true };
          setResult(next);
          setState({ phase: "succeeded", filename: out.filename });
          triggerDownload(next.url, next.filename);
          timerRef.current = setTimeout(() => {
            releaseUpload();
            setState((s) => (s.phase === "succeeded" ? { ...s, expired: true } : s));
          }, DOWNLOAD_GRACE_MS);
        } else {
          setState({ phase: "processing" });
          const out = await runInline({ ...request, slug, signal });
          if (signal.aborted) throw new ToolRunError("cancelled");
          const filename = downloadName ?? out.filename;
          const next: ToolRunResult = { url: URL.createObjectURL(out.blob), filename, remote: false };
          if (out.contentType.startsWith("text/")) {
            next.text = await out.blob.text();
            if (signal.aborted) {
              URL.revokeObjectURL(next.url);
              throw new ToolRunError("cancelled");
            }
          } else {
            triggerDownload(next.url, next.filename);
          }
          setResult(next);
          setState({ phase: "succeeded", filename });
        }
      } catch (error) {
        // Covers failures inside runLargeFlow (it deleted already; deleteUpload is once-per-id)
        // and anything thrown after it returned.
        if (myId !== null && uploadIdRef.current === myId) releaseUpload();
        // A newer run owns the UI once this one was cancelled.
        if (abortRef.current !== null && abortRef.current !== controller) return;
        const err = error instanceof ToolRunError ? error : new ToolRunError("internal_error");
        if (signal.aborted || err.code === "cancelled") {
          setState({ phase: "idle" });
          return;
        }
        setState({ phase: "failed", errorCode: err.code, requestId: err.requestId });
      } finally {
        if (abortRef.current === controller || abortRef.current === null) {
          abortRef.current = null;
          setCancellable(false);
        }
      }
    },
    [limits, releaseUpload, slug],
  );

  const cancel = useCallback(() => {
    abortRun();
    releaseUpload();
    setCancellable(false);
    setState({ phase: "idle" });
  }, [abortRun, releaseUpload]);

  const reset = useCallback(() => {
    abortRun();
    releaseUpload();
    setCancellable(false);
    setResult(null);
    setState({ phase: "idle" });
  }, [abortRun, releaseUpload]);

  const download = useCallback(() => {
    if (result) triggerDownload(result.url, result.filename);
  }, [result]);

  const busy = state.phase === "uploading" || state.phase === "processing";

  return { state, result, busy, cancellable, run, cancel, reset, download };
}
