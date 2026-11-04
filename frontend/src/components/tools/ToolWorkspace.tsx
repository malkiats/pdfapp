"use client";

import { Bot, Copy, Link2, RotateCcw, Type } from "lucide-react";
import dynamic from "next/dynamic";
import { useId, useRef, useState } from "react";
import { useApiLimits, useToolRunner } from "@/hooks/useToolRunner";
import { effectiveCaps, INLINE_FALLBACK_BYTES } from "@/lib/api/uploads";
import { siteConfig } from "@/lib/config/site";
import { formatBytes } from "@/lib/format";
import type { ToolStatus } from "@/types/catalog";
import { FileDropzone, type FileDropzoneRef } from "./FileDropzone";
import { PAGE_WORKSPACE_TOOLS } from "./pageWorkspaces";
import { ProcessingStatus } from "./ProcessingStatus";
import { defaultOptions, missingRequired, ToolForm } from "./ToolForm";

/** Client-only: pdf.js needs the DOM, a worker and canvas. */
const RemovePagesWorkspace = dynamic(
  () => import("./remove-pages/RemovePagesWorkspace").then((m) => m.RemovePagesWorkspace),
  { ssr: false, loading: () => <p className="rounded-2xl border border-border bg-surface p-5 text-sm text-muted">Opening your PDF…</p> },
);

export interface ToolWorkspaceProps {
  toolSlug: string;
  title: string;
  status: ToolStatus;
  inputKinds: ("file" | "url" | "text")[];
  accepts: string[];
  minInputs: number;
  maxInputs: number;
  /** Per-file cap shown to the user (plan display value; the server enforces). */
  maxFileBytes: number;
  requiresAiConsent?: boolean;
}

/** Inline-flow cap used until the server limits are known. */
export const MAX_UPLOAD_BYTES = INLINE_FALLBACK_BYTES;

const fieldClass =
  "mt-1 h-11 w-full rounded-lg border border-border-strong bg-bg px-3 disabled:cursor-not-allowed disabled:bg-surface-strong disabled:text-muted";

/**
 * The interactive area of a tool page. Collects input (files, URLs, text),
 * options and consent, submits inline (POST /api/v1/{slug}) or, for large files,
 * through the upload flow, and shows the result or error.
 */
export function ToolWorkspace(props: ToolWorkspaceProps) {
  const { toolSlug, title, status, inputKinds, accepts, minInputs, maxInputs, maxFileBytes, requiresAiConsent } =
    props;
  const comingSoon = status !== "available";
  const hasFile = inputKinds.includes("file");
  const hasUrl = inputKinds.includes("url");
  const hasText = inputKinds.includes("text");
  const multipleKinds = inputKinds.length > 1;
  const disabledReason = comingSoon ? `${title} is coming soon. Inputs are disabled until it launches.` : undefined;

  const { limits, loaded: limitsLoaded } = useApiLimits();
  const runner = useToolRunner(toolSlug, limits);
  const { state, result, busy } = runner;
  const caps = effectiveCaps(limits, accepts);
  // Until the server limits arrive, accept up to the plan cap; the dropzone re-checks once they do.
  const perFileCap = limitsLoaded ? Math.min(maxFileBytes, caps.perFile) : maxFileBytes;

  const [options, setOptions] = useState<Record<string, unknown>>(() => defaultOptions(toolSlug));
  const [consent, setConsent] = useState(false);
  const [urls, setUrls] = useState({ url1: "", url2: "" });
  const [text, setText] = useState("");
  const [formError, setFormError] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);
  const [formKey, setFormKey] = useState(0);
  const [pageWorkspaceFile, setPageWorkspaceFile] = useState<File | null>(null);

  const fileDropzoneRef = useRef<FileDropzoneRef>(null);
  const urlId = useId();
  const url2Id = useId();
  const textId = useId();
  const consentId = useId();
  const urlCount = hasUrl && !hasText && !hasFile ? Math.min(maxInputs, 2) : 1;
  const locked = comingSoon || busy;
  const pageWorkspace = PAGE_WORKSPACE_TOOLS.has(toolSlug) && !comingSoon && hasFile;

  /** Returns an error message, or null when the inputs are complete. */
  const validate = (files: File[]): string | null => {
    if (files.length > 0 && !limitsLoaded) return "Checking upload limits. Try again in a moment.";
    const urlValues = [urls.url1.trim(), urls.url2.trim()].filter(Boolean);
    const provided = files.length > 0 || urlValues.length > 0 || text.trim() !== "";
    if (!provided) {
      if (multipleKinds) return "Add a file, a link or some text.";
      if (hasFile) return minInputs > 1 ? `Add at least ${minInputs} files.` : "Add a file.";
      if (hasUrl) return urlCount > 1 ? "Enter both page addresses." : "Enter a page address.";
      return "Enter some text.";
    }
    if (files.length > 0 && files.length < minInputs) return `Add at least ${minInputs} files.`;
    if (!multipleKinds && hasUrl && urlValues.length < Math.min(minInputs, urlCount)) return "Enter both page addresses.";
    const total = files.reduce((sum, f) => sum + f.size, 0);
    if (total > caps.total) {
      return `Your files add up to ${formatBytes(total)}. The current limit is ${formatBytes(caps.total)} per request.`;
    }
    const missing = missingRequired(toolSlug, options);
    if (missing.length > 0) return `Fill in: ${missing.join(", ")}.`;
    if (requiresAiConsent && !consent) return "Tick the consent box to send this request to the AI provider.";
    return null;
  };

  const handleProcess = async () => {
    const files = hasFile ? (fileDropzoneRef.current?.getFiles() ?? []) : [];
    const problem = validate(files);
    setFormError(problem);
    if (problem) return;

    await runner.run({
      files,
      options,
      urlA: urls.url1.trim() || undefined,
      urlB: urls.url2.trim() || undefined,
      text: text.trim() ? text : undefined,
      aiConsent: requiresAiConsent ? consent : undefined,
    });
  };

  const handleReset = () => {
    runner.reset();
    setFormError(null);
    setCopied(false);
  };

  const handleStartOver = () => {
    handleReset();
    setUrls({ url1: "", url2: "" });
    setText("");
    setConsent(false);
    setOptions(defaultOptions(toolSlug));
    setPageWorkspaceFile(null);
    setFormKey((k) => k + 1);
  };

  // Open the page workspace only once the file is known to be within the limits.
  if (pageWorkspace && pageWorkspaceFile && limitsLoaded && pageWorkspaceFile.size <= perFileCap) {
    return (
      <section aria-label={`${title} workspace`}>
        <RemovePagesWorkspace file={pageWorkspaceFile} runner={runner} onChangeFile={handleStartOver} />
      </section>
    );
  }

  const copyText = async () => {
    if (!result?.text) return;
    try {
      await navigator.clipboard.writeText(result.text);
      setCopied(true);
    } catch {
      setCopied(false);
    }
  };

  return (
    <section aria-label={`${title} workspace`} className={pageWorkspace ? "max-w-3xl space-y-4" : "space-y-4"}>
      {/* Exactly one coming-soon notice: inside the dropzone for file tools, here otherwise. */}
      {comingSoon && !hasFile ? (
        <p className="rounded-lg border border-warning/40 bg-warning-soft px-4 py-3 text-sm font-medium text-warning">
          {disabledReason}
        </p>
      ) : null}

      {requiresAiConsent ? (
        <p className="flex items-center gap-2 text-sm text-muted">
          <Bot aria-hidden="true" className="size-4 shrink-0" />
          Your content is sent to our AI provider ({siteConfig.aiProviderName}) only with your consent.
        </p>
      ) : null}

      {hasFile ? (
        <FileDropzone
          key={`files-${formKey}`}
          ref={fileDropzoneRef}
          accept={accepts}
          maxFiles={maxInputs}
          minFiles={minInputs}
          maxFileBytes={perFileCap}
          checkingLimits={!limitsLoaded}
          disabled={locked}
          disabledReason={disabledReason}
          onFilesChange={pageWorkspace ? (files) => setPageWorkspaceFile(files[0] ?? null) : undefined}
        />
      ) : null}

      {hasUrl ? (
        <fieldset disabled={locked} className="space-y-3 rounded-2xl border border-border bg-surface p-5">
          <legend className="flex items-center gap-2 px-1 text-sm font-semibold">
            <Link2 aria-hidden="true" className="size-4" />
            {urlCount > 1 ? "Web page addresses" : multipleKinds ? "Web page address (or paste the text below)" : "Web page address"}
          </legend>
          <div>
            <label htmlFor={urlId} className="text-sm text-muted">
              {urlCount > 1 ? "First page URL" : "Page URL"}
            </label>
            <input
              id={urlId}
              type="url"
              inputMode="url"
              placeholder="https://"
              value={urls.url1}
              onChange={(e) => setUrls({ ...urls, url1: e.target.value })}
              className={fieldClass}
            />
          </div>
          {urlCount > 1 ? (
            <div>
              <label htmlFor={url2Id} className="text-sm text-muted">
                Second page URL
              </label>
              <input
                id={url2Id}
                type="url"
                inputMode="url"
                placeholder="https://"
                value={urls.url2}
                onChange={(e) => setUrls({ ...urls, url2: e.target.value })}
                className={fieldClass}
              />
            </div>
          ) : null}
          <p className="text-xs text-muted">Our server fetches public pages on your behalf. Private and internal addresses are refused.</p>
        </fieldset>
      ) : null}

      {hasText ? (
        <fieldset disabled={locked} className="rounded-2xl border border-border bg-surface p-5">
          <legend className="flex items-center gap-2 px-1 text-sm font-semibold">
            <Type aria-hidden="true" className="size-4" />
            {multipleKinds ? "Or paste text" : "Text"}
          </legend>
          <label htmlFor={textId} className="sr-only">
            Text to process
          </label>
          <textarea
            id={textId}
            rows={8}
            maxLength={100_000}
            value={text}
            onChange={(e) => setText(e.target.value)}
            placeholder="Paste your text here"
            className="mt-1 w-full rounded-lg border border-border-strong bg-bg p-3 text-sm disabled:cursor-not-allowed disabled:bg-surface-strong disabled:text-muted"
          />
        </fieldset>
      ) : null}

      {pageWorkspace ? null : (
        <ToolForm key={`options-${formKey}`} toolSlug={toolSlug} disabled={locked} onOptionsChange={setOptions} />
      )}

      {requiresAiConsent ? (
        <label
          htmlFor={consentId}
          className={`flex min-h-11 items-start gap-3 rounded-xl border border-border bg-surface px-4 py-3 text-sm ${
            locked ? "cursor-not-allowed text-muted opacity-70" : "cursor-pointer text-fg"
          }`}
        >
          <input
            id={consentId}
            type="checkbox"
            disabled={locked}
            checked={consent}
            onChange={(e) => setConsent(e.target.checked)}
            className="mt-0.5 size-5 shrink-0 accent-accent disabled:cursor-not-allowed disabled:grayscale"
          />
          <span>
            I agree that the content I submit for this request is sent to our AI provider ({siteConfig.aiProviderName}) to
            produce the result. The provider&apos;s own data-retention terms apply. Consent is asked for every request.
          </span>
        </label>
      ) : null}

      {formError ? (
        <p role="alert" className="rounded-lg border border-danger/40 bg-danger-soft px-4 py-3 text-sm">
          {formError}
        </p>
      ) : null}

      {pageWorkspace ? (
        <p className="text-sm text-muted">Add a PDF to see its pages. Thumbnails are made in your browser.</p>
      ) : !comingSoon && state.phase !== "succeeded" && state.phase !== "failed" ? (
        <button
          onClick={handleProcess}
          type="button"
          disabled={busy}
          className="w-full rounded-lg bg-accent px-4 py-3 text-sm font-medium text-accent-fg hover:bg-accent-hover disabled:cursor-not-allowed disabled:opacity-60"
        >
          {state.phase === "uploading" ? "Uploading…" : busy ? "Processing…" : title}
        </button>
      ) : null}

      <ProcessingStatus
        state={state}
        onDownload={result ? runner.download : undefined}
        onRetry={handleReset}
        onCancel={runner.cancellable ? runner.cancel : undefined}
        focusOnError
      />

      {result?.text !== undefined ? (
        <div className="rounded-2xl border border-border bg-surface p-4">
          <div className="mb-2 flex items-center justify-between gap-2">
            <p className="text-sm font-semibold">Result</p>
            <button
              type="button"
              onClick={copyText}
              className="inline-flex min-h-11 items-center gap-2 rounded-lg border border-border-strong px-3 text-sm hover:bg-surface-strong"
            >
              <Copy aria-hidden="true" className="size-4" />
              {copied ? "Copied" : "Copy"}
            </button>
          </div>
          <pre className="max-h-[32rem] overflow-auto whitespace-pre-wrap break-words text-sm">{result.text}</pre>
        </div>
      ) : null}

      {state.phase === "succeeded" ? (
        <button
          type="button"
          onClick={handleStartOver}
          className="inline-flex min-h-11 items-center gap-2 rounded-lg border border-border-strong px-4 text-sm hover:bg-surface-strong"
        >
          <RotateCcw aria-hidden="true" className="size-4" />
          Process another
        </button>
      ) : null}
    </section>
  );
}
