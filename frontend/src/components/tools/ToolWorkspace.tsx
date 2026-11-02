"use client";

import { Bot, Copy, Link2, RotateCcw, Type } from "lucide-react";
import { useEffect, useId, useRef, useState } from "react";
import { siteConfig } from "@/lib/config/site";
import { apiBaseUrl } from "@/lib/env";
import { formatBytes } from "@/lib/format";
import type { ToolStatus } from "@/types/catalog";
import { FileDropzone, type FileDropzoneRef } from "./FileDropzone";
import { ProcessingStatus, type ProcessingState } from "./ProcessingStatus";
import { defaultOptions, missingRequired, ToolForm } from "./ToolForm";

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

/** The hosting platform rejects request bodies above 4.5 MB; keep headroom for form overhead. */
export const MAX_UPLOAD_BYTES = 4_400_000;

const fieldClass =
  "mt-1 h-11 w-full rounded-lg border border-border-strong bg-bg px-3 disabled:cursor-not-allowed disabled:bg-surface-strong disabled:text-muted";

interface Result {
  url: string;
  filename: string;
  /** Present for text results, which are also shown on the page. */
  text?: string;
}

function filenameFrom(disposition: string | null, fallback: string): string {
  const match = disposition?.match(/filename="([^"]+)"/);
  return match?.[1] ?? fallback;
}

/**
 * The interactive area of a tool page. Collects input (files, URLs, text),
 * options and consent, submits to POST /api/v1/{slug}, and shows the result or error.
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

  const [state, setState] = useState<ProcessingState>({ phase: "idle" });
  const [options, setOptions] = useState<Record<string, unknown>>(() => defaultOptions(toolSlug));
  const [consent, setConsent] = useState(false);
  const [urls, setUrls] = useState({ url1: "", url2: "" });
  const [text, setText] = useState("");
  const [formError, setFormError] = useState<string | null>(null);
  const [result, setResult] = useState<Result | null>(null);
  const [copied, setCopied] = useState(false);
  const [formKey, setFormKey] = useState(0);

  const fileDropzoneRef = useRef<FileDropzoneRef>(null);
  const urlId = useId();
  const url2Id = useId();
  const textId = useId();
  const consentId = useId();
  const urlCount = hasUrl && !hasText && !hasFile ? Math.min(maxInputs, 2) : 1;
  const busy = state.phase === "processing";
  const locked = comingSoon || busy;

  // Free the object URL of a previous result.
  useEffect(() => () => {
    if (result) URL.revokeObjectURL(result.url);
  }, [result]);

  const download = (r: Result | null = result) => {
    if (!r) return;
    const link = document.createElement("a");
    link.href = r.url;
    link.download = r.filename;
    document.body.appendChild(link);
    link.click();
    link.remove();
  };

  /** Returns an error message, or null when the inputs are complete. */
  const validate = (files: File[]): string | null => {
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
    if (total > MAX_UPLOAD_BYTES) {
      return `Your files add up to ${formatBytes(total)}. The current limit is ${formatBytes(MAX_UPLOAD_BYTES)} per request.`;
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

    const formData = new FormData();
    files.forEach((file) => formData.append("files", file));
    if (urls.url1.trim()) formData.append("url_a", urls.url1.trim());
    if (urls.url2.trim()) formData.append("url_b", urls.url2.trim());
    if (text.trim()) formData.append("text", text);
    formData.append("options", JSON.stringify(options));
    if (requiresAiConsent) formData.append("ai_consent", String(consent));

    setResult(null);
    setState({ phase: "processing" });

    let response: Response;
    try {
      response = await fetch(`${apiBaseUrl}/api/v1/${toolSlug}`, { method: "POST", body: formData });
    } catch {
      // Network failure, or a platform error without CORS headers (e.g. upload too large).
      setState({ phase: "failed", errorCode: "network_error" });
      return;
    }

    const requestId = response.headers.get("x-request-id") ?? undefined;
    if (!response.ok) {
      let errorCode: string | null = response.status === 413 ? "file_too_large" : null;
      try {
        const problemBody = (await response.json()) as { code?: string };
        errorCode = problemBody.code ?? errorCode;
      } catch {
        // Not a problem+json body (e.g. a platform error page).
      }
      setState({ phase: "failed", errorCode, requestId });
      return;
    }

    const blob = await response.blob();
    const contentType = response.headers.get("content-type") ?? "";
    const filename = filenameFrom(response.headers.get("content-disposition"), `${toolSlug}-result`);
    const next: Result = { url: URL.createObjectURL(blob), filename };
    if (contentType.startsWith("text/")) {
      next.text = await blob.text();
    } else {
      download(next);
    }
    setResult(next);
    setState({ phase: "succeeded", filename });
  };

  const handleReset = () => {
    setState({ phase: "idle" });
    setResult(null);
    setFormError(null);
    setCopied(false);
  };

  const handleStartOver = () => {
    handleReset();
    setUrls({ url1: "", url2: "" });
    setText("");
    setConsent(false);
    setOptions(defaultOptions(toolSlug));
    setFormKey((k) => k + 1);
  };

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
    <section aria-label={`${title} workspace`} className="space-y-4">
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
          maxFileBytes={Math.min(maxFileBytes, MAX_UPLOAD_BYTES)}
          disabled={locked}
          disabledReason={disabledReason}
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

      <ToolForm key={`options-${formKey}`} toolSlug={toolSlug} disabled={locked} onOptionsChange={setOptions} />

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

      {!comingSoon && state.phase !== "succeeded" && state.phase !== "failed" ? (
        <button
          onClick={handleProcess}
          type="button"
          disabled={busy}
          className="w-full rounded-lg bg-accent px-4 py-3 text-sm font-medium text-accent-fg hover:bg-accent-hover disabled:cursor-not-allowed disabled:opacity-60"
        >
          {busy ? "Processing…" : title}
        </button>
      ) : null}

      <ProcessingStatus state={state} onDownload={result ? () => download() : undefined} onRetry={handleReset} />

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
