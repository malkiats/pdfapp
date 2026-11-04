/**
 * Tool execution transport: the inline multipart flow (POST /api/v1/{slug}) and
 * the large-file flow through presigned storage URLs (shared/openapi.yaml,
 * tag `uploads`):
 *
 *   createUpload -> PUT each file to its put_url -> runUploadedTool -> download_url -> deleteUpload
 *
 * Presigned URLs are secrets: they are never logged, stored or put in error
 * messages. The API is anonymous, so every request uses `credentials: "omit"`.
 */
import { apiBaseUrl, uploadOrigins } from "@/lib/env";
import { MIME_EXTENSIONS } from "@/lib/format";
import type { components } from "./schema";

type Schemas = components["schemas"];
export type ApiLimits = Schemas["Limits"];
export type UploadTarget = Schemas["UploadTarget"];
export type CreateUploadResponse = Schemas["CreateUploadResponse"];
export type UploadResult = Schemas["UploadResult"];
type UploadContentType = Schemas["CreateUploadFile"]["content_type"];

/** The hosting platform rejects request bodies above 4.5 MB; keep headroom for form overhead. */
export const INLINE_FALLBACK_BYTES = 4_400_000;

/** Used until (or if never) GET /api/v1/tools answers: inline only, platform-safe size. */
export const FALLBACK_LIMITS: ApiLimits = {
  max_request_bytes: INLINE_FALLBACK_BYTES,
  max_pages: 100,
  large_files_enabled: false,
  max_large_file_bytes: INLINE_FALLBACK_BYTES,
  max_large_total_bytes: INLINE_FALLBACK_BYTES,
  inline_max_bytes: INLINE_FALLBACK_BYTES,
};

/** Parallel PUTs in the large-file flow. */
const PUT_CONCURRENCY = 3;
const UPLOAD_ID = /^[A-Za-z0-9_-]{32,128}$/;
const UPLOAD_CONTENT_TYPES: readonly UploadContentType[] = [
  "application/pdf",
  "image/jpeg",
  "image/png",
  "image/webp",
  "image/tiff",
];

/** A failed tool run. `code` is a Problem code (or a client code such as `upload_failed`, `cancelled`). */
export class ToolRunError extends Error {
  readonly code: string;
  readonly requestId?: string;
  constructor(code: string, requestId?: string) {
    super(code);
    this.name = "ToolRunError";
    this.code = code;
    this.requestId = requestId;
  }
}

function cancelled(): ToolRunError {
  return new ToolRunError("cancelled");
}

function throwIfAborted(signal?: AbortSignal) {
  if (signal?.aborted) throw cancelled();
}

/** Reads the Problem `code` of an error response, with a status-based fallback. */
async function toRunError(response: Response, fallbacks: Record<number, string> = {}): Promise<ToolRunError> {
  const requestId = response.headers.get("x-request-id") ?? undefined;
  let code: string | null = fallbacks[response.status] ?? (response.status === 413 ? "file_too_large" : null);
  try {
    const body = (await response.json()) as { code?: unknown };
    if (typeof body.code === "string") code = body.code;
  } catch {
    // Not a problem+json body (e.g. a platform error page).
  }
  return new ToolRunError(code ?? "internal_error", requestId);
}

/** Wraps fetch so network failures and aborts become ToolRunErrors. */
async function request(url: string, init: RequestInit): Promise<Response> {
  try {
    return await fetch(url, { credentials: "omit", ...init });
  } catch {
    if (init.signal?.aborted) throw cancelled();
    // Network failure, or a platform error without CORS headers (e.g. upload too large).
    throw new ToolRunError("network_error");
  }
}

/** Origins a presigned URL may point at. */
export interface TrustedOrigins {
  /** PUT targets: the storage origins (NEXT_PUBLIC_UPLOAD_ORIGINS). */
  put: readonly string[];
  /** Download targets: the storage origins and the API origin. */
  download: readonly string[];
}

export function defaultTrustedOrigins(baseUrl: string = apiBaseUrl): TrustedOrigins {
  return { put: uploadOrigins, download: [...uploadOrigins, new URL(baseUrl).origin] };
}

/**
 * True when `value` is an http(s) URL on one of `origins`, and https whenever
 * this page is served over https.
 */
export function isTrustedUrl(value: string, origins: readonly string[]): boolean {
  try {
    const url = new URL(value);
    if (url.protocol !== "https:" && url.protocol !== "http:") return false;
    if (typeof window !== "undefined" && window.location.protocol === "https:" && url.protocol !== "https:") return false;
    return origins.includes(url.origin);
  } catch {
    return false;
  }
}

// ------------------------------------------------------------------ limits

let limitsPromise: Promise<ApiLimits | null> | null = null;

/** GET /api/v1/tools `limits`, cached for the page lifetime. Resolves null when unavailable. */
export function fetchLimits(baseUrl: string = apiBaseUrl): Promise<ApiLimits | null> {
  limitsPromise ??= (async () => {
    try {
      const signal = typeof AbortSignal.timeout === "function" ? AbortSignal.timeout(8000) : undefined;
      const response = await fetch(`${baseUrl}/api/v1/tools`, { credentials: "omit", signal });
      if (!response.ok) return null;
      const body = (await response.json()) as { limits?: ApiLimits };
      return body.limits ?? null;
    } catch {
      return null;
    }
  })().then((limits) => {
    if (!limits) limitsPromise = null; // allow a later retry
    return limits;
  });
  return limitsPromise;
}

/** Test hook: forget the cached limits. */
export function resetLimitsCache() {
  limitsPromise = null;
}

/** True when this file set must go through the large-file flow. */
export function needsLargeFlow(totalBytes: number, limits: ApiLimits): boolean {
  return limits.large_files_enabled && totalBytes > limits.inline_max_bytes;
}

/** True when every type the tool accepts can go through the large-file flow. */
export function acceptsLargeFlow(accepts: readonly string[]): boolean {
  return accepts.length > 0 && accepts.every((mime) => (UPLOAD_CONTENT_TYPES as readonly string[]).includes(mime));
}

/**
 * Per-file and total caps the UI should enforce. The large caps apply only when
 * the flow is enabled and the tool's accepted types can use it.
 */
export function effectiveCaps(limits: ApiLimits, accepts: readonly string[]): { perFile: number; total: number } {
  if (limits.large_files_enabled && acceptsLargeFlow(accepts)) {
    return { perFile: limits.max_large_file_bytes, total: limits.max_large_total_bytes };
  }
  return { perFile: limits.inline_max_bytes, total: limits.inline_max_bytes };
}

// ------------------------------------------------------------------ inline flow

export interface ToolRequestInput {
  slug: string;
  files: File[];
  options: Record<string, unknown>;
  /** Sent only when defined (tools that need AI consent). */
  aiConsent?: boolean;
  text?: string;
  urlA?: string;
  urlB?: string;
  signal?: AbortSignal;
  baseUrl?: string;
}

export interface InlineResult {
  blob: Blob;
  filename: string;
  contentType: string;
}

function filenameFrom(disposition: string | null, fallback: string): string {
  const match = disposition?.match(/filename="([^"]+)"/);
  return match?.[1] ?? fallback;
}

/** POST /api/v1/{slug} as multipart; the result comes back in the response body. */
export async function runInline(input: ToolRequestInput): Promise<InlineResult> {
  const { slug, files, options, aiConsent, text, urlA, urlB, signal, baseUrl = apiBaseUrl } = input;
  const formData = new FormData();
  files.forEach((file) => formData.append("files", file));
  if (urlA) formData.append("url_a", urlA);
  if (urlB) formData.append("url_b", urlB);
  if (text) formData.append("text", text);
  formData.append("options", JSON.stringify(options));
  if (aiConsent !== undefined) formData.append("ai_consent", String(aiConsent));

  const response = await request(`${baseUrl}/api/v1/${slug}`, { method: "POST", body: formData, signal });
  if (!response.ok) throw await toRunError(response);
  let blob: Blob;
  try {
    blob = await response.blob();
  } catch {
    throw signal?.aborted ? cancelled() : new ToolRunError("network_error");
  }
  return {
    blob,
    filename: filenameFrom(response.headers.get("content-disposition"), `${slug}-result`),
    contentType: response.headers.get("content-type") ?? "",
  };
}

// ------------------------------------------------------------------ large-file flow

/** The declared media type for a file, or null when the large-file flow cannot take it. */
export function uploadContentType(file: Pick<File, "name" | "type">): UploadContentType | null {
  if ((UPLOAD_CONTENT_TYPES as readonly string[]).includes(file.type)) return file.type as UploadContentType;
  const lower = file.name.toLowerCase();
  return UPLOAD_CONTENT_TYPES.find((mime) => (MIME_EXTENSIONS[mime] ?? []).some((ext) => lower.endsWith(ext))) ?? null;
}

/** Step 1: POST /api/v1/uploads. */
export async function createUpload(
  slug: string,
  files: File[],
  {
    signal,
    baseUrl = apiBaseUrl,
    origins = defaultTrustedOrigins(baseUrl),
  }: { signal?: AbortSignal; baseUrl?: string; origins?: TrustedOrigins } = {},
): Promise<CreateUploadResponse> {
  const declared = files.map((file) => {
    const contentType = uploadContentType(file);
    if (!contentType) throw new ToolRunError("unsupported_type");
    return { size: file.size, content_type: contentType };
  });
  const response = await request(`${baseUrl}/api/v1/uploads`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ tool: slug, files: declared }),
    signal,
  });
  if (!response.ok) throw await toRunError(response, { 503: "large_files_unavailable" });
  const requestId = response.headers.get("x-request-id") ?? undefined;
  let body: CreateUploadResponse;
  try {
    body = (await response.json()) as CreateUploadResponse;
  } catch {
    throw new ToolRunError("internal_error", requestId);
  }
  const validId = typeof body?.upload_id === "string" && UPLOAD_ID.test(body.upload_id);
  const validTargets =
    Array.isArray(body?.files) &&
    body.files.length === files.length &&
    body.files.every((t) => typeof t.put_url === "string" && isTrustedUrl(t.put_url, origins.put));
  if (!validId || !validTargets) {
    // Never echo the URLs; drop an upload we will not use.
    if (validId) void deleteUpload(body.upload_id, { baseUrl });
    throw new ToolRunError("internal_error", requestId);
  }
  return body;
}

/**
 * Signed headers the client may send on a PUT. Everything else (notably
 * Content-Length, which the browser sets from the Blob) is never set by hand.
 */
function isAllowedPutHeader(name: string): boolean {
  const lower = name.toLowerCase();
  return lower === "content-type" || lower === "content-md5" || lower.startsWith("x-amz-");
}

/**
 * Step 2: PUT one file to its presigned URL with XMLHttpRequest (for upload
 * progress). Sends only allowlisted signed headers (Content-Type, Content-MD5,
 * x-amz-*); Content-Length is set by the browser from the Blob.
 */
export function putFile(
  target: Pick<UploadTarget, "put_url" | "headers">,
  file: Blob,
  { onProgress, signal }: { onProgress?: (loaded: number, total: number) => void; signal?: AbortSignal } = {},
): Promise<void> {
  return new Promise((resolve, reject) => {
    if (signal?.aborted) {
      reject(cancelled());
      return;
    }
    const xhr = new XMLHttpRequest();
    const onAbort = () => xhr.abort();
    const done = (error?: ToolRunError) => {
      signal?.removeEventListener("abort", onAbort);
      if (error) reject(error);
      else resolve();
    };
    xhr.open("PUT", target.put_url);
    for (const [name, value] of Object.entries(target.headers ?? {})) {
      if (isAllowedPutHeader(name)) xhr.setRequestHeader(name, value);
    }
    xhr.upload.onprogress = (event) => {
      onProgress?.(event.loaded, event.lengthComputable ? event.total : file.size);
    };
    xhr.onload = () => {
      if (xhr.status >= 200 && xhr.status < 300) {
        onProgress?.(file.size, file.size);
        done();
      } else {
        done(new ToolRunError("upload_failed"));
      }
    };
    xhr.onerror = () => done(new ToolRunError("upload_failed"));
    xhr.ontimeout = () => done(new ToolRunError("upload_failed"));
    xhr.onabort = () => done(cancelled());
    signal?.addEventListener("abort", onAbort, { once: true });
    xhr.send(file);
  });
}

/** Step 3: POST /api/v1/uploads/{id}/run/{slug}. */
export async function runUploadedTool(
  uploadId: string,
  slug: string,
  body: { options?: Record<string, unknown>; ai_consent?: boolean; text?: string },
  {
    signal,
    baseUrl = apiBaseUrl,
    origins = defaultTrustedOrigins(baseUrl),
  }: { signal?: AbortSignal; baseUrl?: string; origins?: TrustedOrigins } = {},
): Promise<UploadResult> {
  const response = await request(
    `${baseUrl}/api/v1/uploads/${encodeURIComponent(uploadId)}/run/${encodeURIComponent(slug)}`,
    { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body), signal },
  );
  if (!response.ok) {
    throw await toRunError(response, { 409: "upload_incomplete", 503: "large_files_unavailable" });
  }
  const result = (await response.json()) as UploadResult;
  if (typeof result?.download_url !== "string" || !isTrustedUrl(result.download_url, origins.download)) {
    throw new ToolRunError("internal_error", response.headers.get("x-request-id") ?? undefined);
  }
  return result;
}

/** Ids already deleted (or being deleted) on this page: one effective DELETE per id. */
const deletedIds = new Set<string>();

/** Test hook: forget which uploads were deleted. */
export function resetDeletedUploads() {
  deletedIds.clear();
}

const sleep = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms));

/**
 * DELETE /api/v1/uploads/{id}. Best effort and idempotent; sent at most once
 * per id. `keepalive` lets it finish while the page unloads (sendBeacon cannot
 * send DELETE). Outside unload it retries transient failures with backoff.
 */
export async function deleteUpload(
  uploadId: string,
  { baseUrl = apiBaseUrl, unloading = false }: { baseUrl?: string; unloading?: boolean } = {},
): Promise<void> {
  if (!UPLOAD_ID.test(uploadId) || deletedIds.has(uploadId)) return;
  deletedIds.add(uploadId);
  const url = `${baseUrl}/api/v1/uploads/${encodeURIComponent(uploadId)}`;
  const attempts = unloading ? 1 : 3;
  for (let attempt = 0; attempt < attempts; attempt += 1) {
    if (attempt > 0) await sleep(500 * 3 ** (attempt - 1));
    try {
      const response = await fetch(url, { method: "DELETE", credentials: "omit", keepalive: true });
      // 2xx done; 4xx will not get better on retry.
      if (response.status < 500 && response.status !== 429) return;
    } catch {
      // Network failure: retry. The server expires uploads on its own anyway.
    }
  }
}

export type LargeFlowStage = "uploading" | "processing";

export interface LargeFlowInput extends ToolRequestInput {
  origins?: TrustedOrigins;
  /** Called once the upload exists, so the caller can clean it up on unload. */
  onUploadCreated?: (uploadId: string) => void;
  onStage?: (stage: LargeFlowStage) => void;
  /** Per-file upload progress, 0..1, in file order. */
  onProgress?: (perFile: number[]) => void;
}

export interface LargeFlowResult extends UploadResult {
  uploadId: string;
}

/**
 * Runs the whole large-file flow up to the download URL. On any failure or
 * cancel after createUpload, the upload is deleted before the error is rethrown.
 * On success the caller downloads, then calls deleteUpload(uploadId).
 */
export async function runLargeFlow(input: LargeFlowInput): Promise<LargeFlowResult> {
  const { slug, files, options, aiConsent, text, signal, baseUrl = apiBaseUrl, onUploadCreated, onStage, onProgress } = input;
  const origins = input.origins ?? defaultTrustedOrigins(baseUrl);
  onStage?.("uploading");
  const upload = await createUpload(slug, files, { signal, baseUrl, origins });
  const uploadId = upload.upload_id;
  onUploadCreated?.(uploadId);

  try {
    throwIfAborted(signal);
    const progress = files.map(() => 0);
    onProgress?.([...progress]);
    const targets = [...upload.files].sort((a, b) => a.index - b.index);
    // One failed PUT stops the others.
    const puts = new AbortController();
    const stopPuts = () => puts.abort();
    signal?.addEventListener("abort", stopPuts, { once: true });
    let next = 0;
    const worker = async () => {
      while (next < targets.length) {
        const target = targets[next++]!;
        const file = files[target.index];
        if (!file) throw new ToolRunError("internal_error");
        await putFile(target, file, {
          signal: puts.signal,
          onProgress: (loaded, total) => {
            progress[target.index] = total > 0 ? Math.min(1, loaded / total) : 1;
            onProgress?.([...progress]);
          },
        });
      }
    };
    try {
      await Promise.all(
        Array.from({ length: Math.min(PUT_CONCURRENCY, targets.length) }, () =>
          worker().catch((error: unknown) => {
            puts.abort();
            throw error;
          }),
        ),
      );
    } finally {
      signal?.removeEventListener("abort", stopPuts);
    }

    throwIfAborted(signal);
    onStage?.("processing");
    const body: { options: Record<string, unknown>; ai_consent?: boolean; text?: string } = { options };
    if (aiConsent !== undefined) body.ai_consent = aiConsent;
    if (text) body.text = text;
    const result = await runUploadedTool(uploadId, slug, body, { signal, baseUrl, origins });
    return { ...result, uploadId };
  } catch (error) {
    void deleteUpload(uploadId, { baseUrl });
    throw error instanceof ToolRunError ? error : new ToolRunError(signal?.aborted ? "cancelled" : "internal_error");
  }
}

/** Starts a browser download of a URL without reading it into memory. */
export function triggerDownload(url: string, filename: string) {
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  link.rel = "noopener noreferrer";
  link.referrerPolicy = "no-referrer";
  document.body.appendChild(link);
  link.click();
  link.remove();
}

/**
 * A safe local filename `<basename><suffix>.<ext>` derived from the user's file
 * name, e.g. ("My report (v2).pdf", "-removed") -> "My report (v2)-removed.pdf".
 */
export function derivedFilename(original: string, suffix: string, ext: string): string {
  const base = original
    .replace(/\.[^./\\]+$/, "")
    .replace(/[^\p{L}\p{N} ._()-]+/gu, "_")
    .replace(/^[\s._-]+|[\s._-]+$/g, "")
    .slice(0, 100);
  return `${base || "document"}${suffix}.${ext}`;
}
