import { AlertCircle, CheckCircle2, Download, Loader2, ShieldCheck } from "lucide-react";
import type { ReactNode } from "react";
import { errorMessage } from "@/lib/api/errors";
import { retentionSentence } from "@/lib/config/retention";

/**
 * UI state for a synchronous tool request.
 * - idle: waiting for user input
 * - processing: POST in flight with request ID
 * - succeeded: got a 200 response with result
 * - failed: got an error response
 */
export type ProcessingState =
  | { phase: "idle" }
  | { phase: "processing"; requestId?: string }
  | { phase: "succeeded"; filename?: string }
  | { phase: "failed"; errorCode: string | null; requestId?: string };

export interface ProcessingStatusProps {
  state: ProcessingState;
  onDownload?: () => void;
  onRetry?: () => void;
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

/** Processing state UI for a synchronous tool request. */
export function ProcessingStatus({ state, onDownload, onRetry }: ProcessingStatusProps) {
  let content: ReactNode = null;

  switch (state.phase) {
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
        </Panel>
      );
      break;

    case "succeeded":
      content = (
        <Panel tone="success" icon={<CheckCircle2 aria-hidden="true" className="size-5 text-success" />} title="Your result is ready">
          <p className="mt-1 text-sm text-muted">{retentionSentence}</p>
          {onDownload ? (
            <button type="button" onClick={onDownload} className={`${buttonClass} mt-3 bg-accent text-accent-fg hover:bg-accent-hover`}>
              <Download aria-hidden="true" className="size-4" />
              Download result
            </button>
          ) : null}
        </Panel>
      );
      break;

    case "failed":
      content = (
        <Panel tone="danger" icon={<AlertCircle aria-hidden="true" className="size-5 text-danger" />} title="Processing failed">
          <p className="mt-1 text-sm">{errorMessage(state.errorCode)}</p>
          {state.requestId ? (
            <p className="mt-1 text-xs text-muted">
              Reference: <code>{state.requestId}</code>
            </p>
          ) : null}
          {onRetry ? (
            <button type="button" onClick={onRetry} className={`${buttonClass} mt-3 border border-border-strong bg-bg hover:bg-surface-strong`}>
              Try again
            </button>
          ) : null}
        </Panel>
      );
      break;
  }

  return (
    <div role="status" aria-live="polite" aria-atomic="true" data-phase={state.phase}>
      {content}
    </div>
  );
}
