"use client";

import { AlertCircle, CheckCircle2, Download, Loader2, ShieldCheck, UploadCloud } from "lucide-react";
import { useEffect, useRef, type ReactNode } from "react";
import { errorMessage } from "@/lib/api/errors";
import { retentionSentence } from "@/lib/config/retention";

/**
 * UI state for a synchronous tool request.
 * - idle: waiting for user input
 * - uploading: large-file flow, files going to storage (progress per file, 0..1)
 * - processing: POST in flight with request ID
 * - succeeded: got a 200 response with result (`expired` once a large-file result was cleaned up)
 * - failed: got an error response
 */
export type ProcessingState =
  | { phase: "idle" }
  | { phase: "uploading"; progress: number[] }
  | { phase: "processing"; requestId?: string }
  | { phase: "succeeded"; filename?: string; expired?: boolean }
  | { phase: "failed"; errorCode: string | null; requestId?: string };

export interface ProcessingStatusProps {
  state: ProcessingState;
  onDownload?: () => void;
  onRetry?: () => void;
  /** Shown while uploading or processing when the request can be cancelled. */
  onCancel?: () => void;
  /** Label of the failure action (default "Try again"). */
  retryLabel?: string;
  /** Move keyboard focus to the error when a request fails. */
  focusOnError?: boolean;
}

/** Overall upload progress in whole percent. */
export function overallPercent(progress: readonly number[]): number {
  if (progress.length === 0) return 0;
  return Math.floor((progress.reduce((sum, p) => sum + p, 0) / progress.length) * 100);
}

function Panel({ tone, icon, title, children }: { tone: "neutral" | "success" | "danger"; icon: ReactNode; title: string; children?: ReactNode }) {
  const toneClass =
    tone === "success"
      ? "border-success/40 bg-success-soft"
      : tone === "danger"
        ? "border-danger/40 bg-danger-soft"
        : "border-border bg-surface";
  return (
    <div className={`rounded-xl border p-4 ${toneClass}`}>
      <div className="flex items-start gap-3">
        <span className="mt-0.5 shrink-0">{icon}</span>
        <div className="min-w-0 flex-1">
          <p className="font-semibold">{title}</p>
          {children}
        </div>
      </div>
    </div>
  );
}

const buttonClass =
  "inline-flex items-center gap-2 rounded-lg px-4 py-2 text-sm font-medium disabled:cursor-not-allowed disabled:opacity-60";

/** Determinate upload progress bar (also used by the small-screen action bar). */
export function UploadProgressBar({ percent, className = "" }: { percent: number; className?: string }) {
  return (
    <div
      role="progressbar"
      aria-label="Upload progress"
      aria-valuemin={0}
      aria-valuemax={100}
      aria-valuenow={percent}
      className={`h-2 w-full overflow-hidden rounded-full bg-surface-strong ${className}`}
    >
      <div className="h-full rounded-full bg-accent transition-[width]" style={{ width: `${percent}%` }} />
    </div>
  );
}

/** Processing state UI for a synchronous tool request. */
export function ProcessingStatus({
  state,
  onDownload,
  onRetry,
  onCancel,
  retryLabel = "Try again",
  focusOnError = false,
}: ProcessingStatusProps) {
  let content: ReactNode = null;
  const alertRef = useRef<HTMLDivElement>(null);
  const failed = state.phase === "failed";
  useEffect(() => {
    if (failed && focusOnError) alertRef.current?.focus();
  }, [failed, focusOnError]);
  const cancelButton = onCancel ? (
    <button type="button" onClick={onCancel} className={`${buttonClass} mt-3 min-h-11 border border-border-strong bg-bg hover:bg-surface-strong`}>
      Cancel
    </button>
  ) : null;

  switch (state.phase) {
    case "uploading": {
      const percent = overallPercent(state.progress);
      content = (
        <Panel tone="neutral" icon={<UploadCloud aria-hidden="true" className="size-5 text-accent" />} title={`Uploading (${percent}%)`}>
          <UploadProgressBar percent={percent} className="mt-2" />
          {state.progress.length > 1 ? (
            <ul className="mt-2 space-y-0.5 text-xs text-muted">
              {state.progress.map((p, i) => (
                <li key={i}>
                  File {i + 1} of {state.progress.length}: {Math.floor(p * 100)}%
                </li>
              ))}
            </ul>
          ) : null}
          <p className="mt-2 text-sm text-muted">Large files are uploaded to temporary storage first, then processed.</p>
          {cancelButton}
        </Panel>
      );
      break;
    }

    case "idle":
      content = (
        <Panel tone="neutral" icon={<ShieldCheck aria-hidden="true" className="size-5 text-success" />} title="What happens to your files">
          <p className="mt-1 text-sm text-muted">{retentionSentence}</p>
        </Panel>
      );
      break;

    case "processing":
      content = (
        <Panel tone="neutral" icon={<Loader2 aria-hidden="true" className="size-5 animate-spin text-accent" />} title="Processing">
          <p className="mt-1 text-sm text-muted">Working on it, this typically takes a few seconds.</p>
          {state.requestId ? (
            <p className="mt-1 text-xs text-muted">
              Request ID: <code>{state.requestId}</code>
            </p>
          ) : null}
          {cancelButton}
        </Panel>
      );
      break;

    case "succeeded":
      content = (
        <Panel tone="success" icon={<CheckCircle2 aria-hidden="true" className="size-5 text-success" />} title="Your result is ready">
          <p className="mt-1 text-sm text-muted">
            {state.expired ? "The download link has expired and the files were deleted. Process the file again to get a new copy." : retentionSentence}
          </p>
          {onDownload && !state.expired ? (
            <button
              type="button"
              data-action="download"
              onClick={onDownload}
              className={`${buttonClass} mt-3 min-h-11 bg-accent text-accent-fg hover:bg-accent-hover`}
            >
              <Download aria-hidden="true" className="size-4" />
              Download result
            </button>
          ) : null}
        </Panel>
      );
      break;

    case "failed":
      content = (
        <div ref={alertRef} role="alert" tabIndex={-1} className="rounded-xl">
          <Panel tone="danger" icon={<AlertCircle aria-hidden="true" className="size-5 text-danger" />} title="Processing failed">
            <p className="mt-1 text-sm">{errorMessage(state.errorCode)}</p>
            {state.requestId ? (
              <p className="mt-1 text-xs text-muted">
                Reference: <code>{state.requestId}</code>
              </p>
            ) : null}
            {onRetry ? (
              <button type="button" onClick={onRetry} className={`${buttonClass} mt-3 border border-border-strong bg-bg hover:bg-surface-strong`}>
                {retryLabel}
              </button>
            ) : null}
          </Panel>
        </div>
      );
      break;
  }

  return (
    // The failure is its own alert region; keep the polite status region for everything else.
    <div role={failed ? undefined : "status"} aria-live={failed ? undefined : "polite"} aria-atomic="true" data-phase={state.phase}>
      {content}
    </div>
  );
}
