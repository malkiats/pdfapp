"use client";

import { Bot, Link2 } from "lucide-react";
import { useId, useRef, useState } from "react";
import { siteConfig } from "@/lib/config/site";
import { apiBaseUrl } from "@/lib/env";
import type { ToolStatus } from "@/types/catalog";
import { FileDropzone, type FileDropzoneRef } from "./FileDropzone";
import { ProcessingStatus, type ProcessingState } from "./ProcessingStatus";
import { ToolForm } from "./ToolForm";

export interface ToolWorkspaceProps {
  toolSlug: string;
  title: string;
  status: ToolStatus;
  inputKinds: ("file" | "url")[];
  accepts: string[];
  minInputs: number;
  maxInputs: number;
  /** Per-file cap shown to the user (plan display value; the server enforces). */
  maxFileBytes: number;
  requiresAiConsent?: boolean;
}

const fieldClass =
  "mt-1 h-11 w-full rounded-lg border border-border-strong bg-bg px-3 disabled:cursor-not-allowed disabled:bg-surface-strong disabled:text-muted";

/**
 * The interactive area of a tool page. Collects input (files, URLs, text),
 * options, consent, submits to POST /api/v1/{slug}, and displays result or error.
 */
export function ToolWorkspace(props: ToolWorkspaceProps) {
  const {
    toolSlug,
    title,
    status,
    inputKinds,
    accepts,
    minInputs,
    maxInputs,
    maxFileBytes,
    requiresAiConsent,
  } = props;
  const comingSoon = status !== "available";
  const hasFile = inputKinds.includes("file");
  const disabledReason = comingSoon ? `${title} is coming soon. Inputs are disabled until it launches.` : undefined;

  const [state, setState] = useState<ProcessingState>({ phase: "idle" });
  const [options, setOptions] = useState<Record<string, unknown>>({});
  const [consent, setConsent] = useState(false);
  const [urls, setUrls] = useState({ url1: "", url2: "" });

  const fileDropzoneRef = useRef<FileDropzoneRef>(null);
  const urlId = useId();
  const url2Id = useId();
  const consentId = useId();
  const urlCount = Math.min(maxInputs, 2);

  const handleProcess = async () => {
    // Validate inputs
    let hasInput = false;
    let files: File[] = [];

    if (hasFile) {
      files = fileDropzoneRef.current?.getFiles() || [];
      if (files.length === 0) {
        alert("Please select at least one file");
        return;
      }
      hasInput = true;
    }

    if (inputKinds.includes("url")) {
      if (!urls.url1.trim()) {
        alert("Please enter at least one URL");
        return;
      }
      hasInput = true;
    }


    if (!hasInput) {
      alert("Please provide input");
      return;
    }

    if (requiresAiConsent && !consent) {
      alert("Please give consent to send your content to the AI provider");
      return;
    }

    // Build FormData
    const formData = new FormData();

    // Add files if present
    if (hasFile) {
      files.forEach((file) => {
        formData.append("files", file);
      });
    }

    // Add URLs if present
    if (inputKinds.includes("url")) {
      if (urls.url1.trim()) formData.append("url_a", urls.url1);
      if (urls.url2 && urls.url2.trim()) formData.append("url_b", urls.url2);
    }


    // Add options if any
    if (Object.keys(options).length > 0) {
      formData.append("options", JSON.stringify(options));
    }

    // Submit
    setState({ phase: "processing", requestId: "processing..." });

    try {
      // Call the tool endpoint dynamically
      // POST /api/v1/{toolSlug}
      const endpoint = `/api/v1/${toolSlug}`;
      const url = `${apiBaseUrl}${endpoint}`;

      const response = await fetch(url, {
        method: "POST",
        body: formData,
        credentials: "include",
      });

      const responseHeaders = Object.fromEntries(response.headers.entries());
      const requestId = responseHeaders["x-request-id"];

      if (!response.ok) {
        // Handle error response (RFC 9457 Problem)
        let errorCode: string | null = null;
        try {
          const error = (await response.json()) as { code?: string; request_id?: string };
          errorCode = error.code || null;
        } catch {
          // Ignore parsing errors, use a generic code
        }
        setState({
          phase: "failed",
          errorCode,
          requestId,
        });
        return;
      }

      // Success: get the result
      const contentType = response.headers.get("content-type") || "";
      const contentDisposition = response.headers.get("content-disposition") || "";

      // Extract filename from Content-Disposition
      let filename = "result";
      const match = contentDisposition.match(/filename="([^"]+)"/);
      if (match?.[1]) {
        filename = match[1];
      }

      if (contentType.startsWith("application/json")) {
        // JSON response (e.g., compare-sites)
        // eslint-disable-next-line @typescript-eslint/no-unused-vars
        const _result = await response.json();
        setState({ phase: "succeeded", filename });
        // Store result for download as JSON
        // (In a real app, you might render the JSON or offer a download)
      } else {
        // File response (PDF, ZIP, etc.)
        const blob = await response.blob();
        // Trigger download
        const url = URL.createObjectURL(blob);
        const link = document.createElement("a");
        link.href = url;
        link.download = filename;
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
        URL.revokeObjectURL(url);

        setState({ phase: "succeeded", filename });
      }
    } catch {
      setState({
        phase: "failed",
        errorCode: "internal_error",
        requestId: undefined,
      });
    }
  };

  const handleRetry = () => {
    setState({ phase: "idle" });
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
          Your text is sent to our AI provider ({siteConfig.aiProviderName}) only with your consent.
        </p>
      ) : null}

      {hasFile ? (
        <FileDropzone
          ref={fileDropzoneRef}
          accept={accepts}
          maxFiles={maxInputs}
          minFiles={minInputs}
          maxFileBytes={maxFileBytes}
          disabled={comingSoon}
          disabledReason={disabledReason}
        />
      ) : null}

      {inputKinds.includes("url") ? (
        <fieldset disabled={comingSoon} className="space-y-3 rounded-2xl border border-border bg-surface p-5">
          <legend className="flex items-center gap-2 px-1 text-sm font-semibold">
            <Link2 aria-hidden="true" className="size-4" />
            {urlCount > 1 ? "Web page addresses" : "Web page address"}
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
              disabled={comingSoon || state.phase !== "idle"}
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
                disabled={comingSoon || state.phase !== "idle"}
                value={urls.url2}
                onChange={(e) => setUrls({ ...urls, url2: e.target.value })}
                className={fieldClass}
              />
            </div>
          ) : null}
          <p className="text-xs text-muted">Our server fetches public pages on your behalf. Private and internal addresses are refused.</p>
        </fieldset>
      ) : null}


      <ToolForm toolSlug={toolSlug} onOptionsChange={setOptions} />

      {requiresAiConsent ? (
        <label
          htmlFor={consentId}
          className={`flex min-h-11 items-start gap-3 rounded-xl border border-border bg-surface px-4 py-3 text-sm ${
            comingSoon || state.phase !== "idle" ? "cursor-not-allowed text-muted opacity-70" : "cursor-pointer text-fg"
          }`}
        >
          <input
            id={consentId}
            type="checkbox"
            disabled={comingSoon || state.phase !== "idle"}
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

      {state.phase === "idle" && !comingSoon ? (
        <button
          onClick={handleProcess}
          type="button"
          className="w-full rounded-lg bg-accent px-4 py-3 text-sm font-medium text-accent-fg hover:bg-accent-hover disabled:cursor-not-allowed disabled:opacity-60"
        >
          Process
        </button>
      ) : null}

      <ProcessingStatus
        state={state}
        onDownload={() => handleRetry()}
        onRetry={handleRetry}
      />
    </section>
  );
}
