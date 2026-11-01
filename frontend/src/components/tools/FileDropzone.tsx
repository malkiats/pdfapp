"use client";

import { FileText, Upload, X } from "lucide-react";
import { useId, useRef, useState, forwardRef, useImperativeHandle, type DragEvent } from "react";
import { acceptLabel, formatBytes, MIME_EXTENSIONS } from "@/lib/format";

export interface FileDropzoneProps {
  /** Accepted MIME types (from the catalog `accepts`). Empty means any type. */
  accept: readonly string[];
  /** Maximum number of files (catalog `max_inputs`, possibly lowered by the tier cap). */
  maxFiles: number;
  /** Minimum number of files the tool needs (catalog `min_inputs`); shown as a hint. */
  minFiles?: number;
  /** Per-file size cap in bytes. UI hint only: the server enforces the real limit. */
  maxFileBytes: number;
  disabled?: boolean;
  /** Explains why the zone is disabled, e.g. "This tool is coming soon". */
  disabledReason?: string;
  label?: string;
  /** Called with the full current selection after every change. */
  onFilesChange?: (files: File[]) => void;
}

export interface FileDropzoneRef {
  getFiles(): File[];
}

export interface RejectedFile {
  name: string;
  reason: string;
}

/**
 * Client-side pre-check only: the server decides by magic-byte sniffing. True
 * when the file matches an accepted MIME type or one of its extensions. If the
 * tool accepts a MIME type this UI has no extension mapping for, the check
 * fails open (the file is allowed through and the server decides).
 */
export function isAccepted(file: Pick<File, "name" | "type">, accept: readonly string[]): boolean {
  if (accept.length === 0) return true;
  if (file.type && accept.includes(file.type)) return true;
  const lower = file.name.toLowerCase();
  if (accept.some((mime) => (MIME_EXTENSIONS[mime] ?? []).some((ext) => lower.endsWith(ext)))) return true;
  return accept.some((mime) => !(mime in MIME_EXTENSIONS));
}

/** Splits incoming files into accepted additions and rejections, respecting type, size and count limits. */
export function validateFiles(
  incoming: readonly File[],
  existing: readonly File[],
  { accept, maxFiles, maxFileBytes }: Pick<FileDropzoneProps, "accept" | "maxFiles" | "maxFileBytes">,
): { accepted: File[]; rejected: RejectedFile[] } {
  const accepted: File[] = [];
  const rejected: RejectedFile[] = [];
  for (const file of incoming) {
    if (!isAccepted(file, accept)) {
      rejected.push({ name: file.name, reason: `not a supported file type (${acceptLabel(accept)})` });
    } else if (file.size > maxFileBytes) {
      rejected.push({ name: file.name, reason: `larger than ${formatBytes(maxFileBytes)}` });
    } else if (file.size === 0) {
      rejected.push({ name: file.name, reason: "the file is empty" });
    } else if (existing.length + accepted.length >= maxFiles) {
      rejected.push({ name: file.name, reason: `you can add up to ${maxFiles} ${maxFiles === 1 ? "file" : "files"}` });
    } else {
      accepted.push(file);
    }
  }
  return { accepted, rejected };
}

/**
 * Drag-and-drop file picker. Keyboard users use the "Choose files" button
 * (a real button that opens the native picker). Selected file names stay in
 * the browser; they are shown here only for the user's benefit.
 * Exported as a ref with a getFiles() method.
 */
export const FileDropzone = forwardRef<FileDropzoneRef, FileDropzoneProps>(function FileDropzone(
  {
    accept,
    maxFiles,
    minFiles = 1,
    maxFileBytes,
    disabled = false,
    disabledReason,
    label = "Choose files",
    onFilesChange,
  },
  ref,
) {
  const [files, setFiles] = useState<File[]>([]);
  const [rejected, setRejected] = useState<RejectedFile[]>([]);
  const [dragging, setDragging] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);
  const hintId = useId();
  const errorId = useId();
  const reasonId = useId();

  // Expose getFiles via ref
  useImperativeHandle(ref, () => ({
    getFiles: () => files,
  }));

  const acceptAttr = accept.flatMap((mime) => [mime, ...(MIME_EXTENSIONS[mime] ?? [])]).join(",");
  const multiple = maxFiles > 1;

  const update = (next: File[]) => {
    setFiles(next);
    onFilesChange?.(next);
  };

  const addFiles = (incoming: File[]) => {
    if (disabled || incoming.length === 0) return;
    const result = validateFiles(incoming, files, { accept, maxFiles, maxFileBytes });
    setRejected(result.rejected);
    if (result.accepted.length > 0) update([...files, ...result.accepted]);
  };

  const removeAt = (index: number) => {
    update(files.filter((_, i) => i !== index));
    setRejected([]);
  };

  const onDragOver = (event: DragEvent<HTMLDivElement>) => {
    event.preventDefault();
    if (disabled) {
      event.dataTransfer.dropEffect = "none";
      return;
    }
    event.dataTransfer.dropEffect = "copy";
    setDragging(true);
  };

  const onDrop = (event: DragEvent<HTMLDivElement>) => {
    event.preventDefault();
    setDragging(false);
    addFiles(Array.from(event.dataTransfer.files));
  };

  const describedBy = [hintId, rejected.length > 0 ? errorId : null, disabled && disabledReason ? reasonId : null]
    .filter(Boolean)
    .join(" ");

  return (
    <div className="w-full">
      <div
        data-testid="dropzone"
        data-dragging={dragging || undefined}
        aria-disabled={disabled || undefined}
        onDragOver={onDragOver}
        onDragEnter={onDragOver}
        onDragLeave={() => setDragging(false)}
        onDrop={onDrop}
        className={[
          "flex flex-col items-center justify-center rounded-2xl border-2 border-dashed px-6 py-10 text-center transition-colors",
          disabled
            ? "cursor-not-allowed border-border bg-surface opacity-80"
            : dragging
              ? "border-accent bg-accent-soft"
              : "border-border-strong bg-surface hover:border-accent",
        ].join(" ")}
      >
        <Upload aria-hidden="true" className={`size-10 ${disabled ? "text-muted" : "text-accent"}`} />
        <p className="mt-4 text-lg font-semibold">{disabled ? "Uploads are not open yet" : "Drop files here"}</p>
        <p id={hintId} className="mt-1 text-sm text-muted">
          {accept.length > 0 ? `${acceptLabel(accept)}` : "Any file"} · up to {formatBytes(maxFileBytes)} each ·{" "}
          {minFiles > 1 ? `${minFiles} to ${maxFiles} files` : maxFiles === 1 ? "1 file" : `up to ${maxFiles} files`}
        </p>
        {disabled && disabledReason ? (
          <p id={reasonId} className="mt-3 rounded-lg bg-warning-soft px-3 py-1.5 text-sm font-medium text-warning">
            {disabledReason}
          </p>
        ) : null}
        <button
          type="button"
          disabled={disabled}
          onClick={() => inputRef.current?.click()}
          aria-describedby={describedBy || undefined}
          className="mt-5 inline-flex items-center gap-2 rounded-lg bg-accent px-5 py-2.5 font-medium text-accent-fg hover:bg-accent-hover disabled:cursor-not-allowed disabled:bg-border-strong disabled:text-muted"
        >
          {label}
        </button>
        <input
          ref={inputRef}
          type="file"
          tabIndex={-1}
          aria-hidden="true"
          className="hidden"
          accept={acceptAttr || undefined}
          multiple={multiple}
          disabled={disabled}
          data-testid="file-input"
          onChange={(event) => {
            addFiles(Array.from(event.target.files ?? []));
            event.target.value = "";
          }}
        />
        <p className="mt-4 text-xs text-muted">File names stay in your browser and are never stored.</p>
      </div>

      {rejected.length > 0 ? (
        <div id={errorId} role="alert" className="mt-3 rounded-lg bg-danger-soft px-4 py-3 text-sm text-danger">
          <p className="font-medium">
            {rejected.length === 1 ? "1 file was not added:" : `${rejected.length} files were not added:`}
          </p>
          <ul className="mt-1 list-disc pl-5">
            {rejected.map((r, i) => (
              <li key={`${r.name}-${i}`}>
                <span className="break-all">{r.name}</span>: {r.reason}
              </li>
            ))}
          </ul>
        </div>
      ) : null}

      {files.length > 0 ? (
        <div className="mt-4">
          <h3 className="text-sm font-semibold">
            Selected files ({files.length}/{maxFiles})
          </h3>
          <ul aria-label="Selected files" className="mt-2 divide-y divide-border rounded-xl border border-border">
            {files.map((file, index) => (
              <li key={`${file.name}-${file.size}-${index}`} className="flex items-center gap-3 px-4 py-2.5">
                <FileText aria-hidden="true" className="size-5 shrink-0 text-muted" />
                <span className="min-w-0 flex-1 truncate text-sm" title={file.name}>
                  {file.name}
                </span>
                <span className="shrink-0 text-xs text-muted">{formatBytes(file.size)}</span>
                <button
                  type="button"
                  onClick={() => removeAt(index)}
                  className="inline-flex size-8 shrink-0 items-center justify-center rounded-md text-muted hover:bg-surface-strong hover:text-fg"
                >
                  <X aria-hidden="true" className="size-4" />
                  <span className="sr-only">Remove {file.name}</span>
                </button>
              </li>
            ))}
          </ul>
          {files.length < minFiles ? (
            <p className="mt-2 text-sm text-muted">
              Add at least {minFiles - files.length} more {minFiles - files.length === 1 ? "file" : "files"} to continue.
            </p>
          ) : null}
        </div>
      ) : null}
    </div>
  );
});
