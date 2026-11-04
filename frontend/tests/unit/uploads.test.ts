import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import {
  createUpload,
  deleteUpload,
  effectiveCaps,
  FALLBACK_LIMITS,
  fetchLimits,
  needsLargeFlow,
  putFile,
  resetDeletedUploads,
  resetLimitsCache,
  runInline,
  runLargeFlow,
  ToolRunError,
  uploadContentType,
  derivedFilename,
  isTrustedUrl,
  type ApiLimits,
} from "@/lib/api/uploads";

const BASE = "http://api.test";
const UPLOAD_ID = "u_Zk3p9Qx1Lm7Rt5Vb2Nc8Hd4Jf6Sg0Wa";
const PUT_URL = (i: number) => `https://storage.test/uploads/opaque-${i}?signature=SECRET`;
const ORIGINS = { put: ["https://storage.test"], download: ["https://storage.test", BASE] };
const LIMITS: ApiLimits = {
  max_request_bytes: 26_214_400,
  max_pages: 500,
  large_files_enabled: true,
  max_large_file_bytes: 100 * 1024 * 1024,
  max_large_total_bytes: 200 * 1024 * 1024,
  inline_max_bytes: 4_194_304,
};

const pdf = (name = "a.pdf", size = 10) => new File([new Uint8Array(size)], name, { type: "application/pdf" });

function json(body: unknown, status = 200, headers: Record<string, string> = {}) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": status >= 400 ? "application/problem+json" : "application/json", ...headers },
  });
}

/** Minimal XMLHttpRequest stand-in: records the request and answers with `FakeXHR.status`. */
class FakeXHR {
  static instances: FakeXHR[] = [];
  static status = 200;
  static auto = true;
  method = "";
  url = "";
  headers: Record<string, string> = {};
  body: unknown = null;
  status = 0;
  upload: { onprogress: ((e: { loaded: number; total: number; lengthComputable: boolean }) => void) | null } = {
    onprogress: null,
  };
  onload: (() => void) | null = null;
  onerror: (() => void) | null = null;
  onabort: (() => void) | null = null;
  ontimeout: (() => void) | null = null;
  constructor() {
    FakeXHR.instances.push(this);
  }
  open(method: string, url: string) {
    this.method = method;
    this.url = url;
  }
  setRequestHeader(name: string, value: string) {
    if (name.toLowerCase() === "content-length") throw new Error("Refused to set unsafe header");
    this.headers[name] = value;
  }
  send(body: Blob) {
    this.body = body;
    if (FakeXHR.auto) queueMicrotask(() => this.respond(FakeXHR.status));
  }
  respond(status: number) {
    const size = (this.body as Blob).size;
    this.upload.onprogress?.({ loaded: size / 2, total: size, lengthComputable: true });
    this.status = status;
    this.onload?.();
  }
  abort() {
    this.onabort?.();
  }
}

let fetchMock: ReturnType<typeof vi.fn<(url: string, init?: RequestInit) => Promise<Response>>>;

beforeEach(() => {
  FakeXHR.instances = [];
  FakeXHR.status = 200;
  FakeXHR.auto = true;
  vi.stubGlobal("XMLHttpRequest", FakeXHR);
  fetchMock = vi.fn<(url: string, init?: RequestInit) => Promise<Response>>();
  vi.stubGlobal("fetch", fetchMock);
  resetLimitsCache();
  resetDeletedUploads();
});

afterEach(() => {
  vi.unstubAllGlobals();
});

/** Routes fetch calls by method + path. */
function routes(table: Record<string, (init?: RequestInit) => Response | Promise<Response>>) {
  fetchMock.mockImplementation(async (url, init) => {
    const key = `${init?.method ?? "GET"} ${new URL(url).pathname}`;
    const handler = table[key];
    if (!handler) throw new Error(`unexpected ${key}`);
    return handler(init);
  });
}

describe("limits and routing", () => {
  it("uses the large flow only above inline_max_bytes and when enabled", () => {
    expect(needsLargeFlow(4_194_304, LIMITS)).toBe(false);
    expect(needsLargeFlow(4_194_305, LIMITS)).toBe(true);
    expect(needsLargeFlow(50_000_000, { ...LIMITS, large_files_enabled: false })).toBe(false);
  });

  it("caps per file and in total by the large limits when enabled, else by the inline limit", () => {
    const pdfOnly = ["application/pdf"];
    expect(effectiveCaps(LIMITS, pdfOnly)).toEqual({ perFile: LIMITS.max_large_file_bytes, total: LIMITS.max_large_total_bytes });
    expect(effectiveCaps({ ...LIMITS, large_files_enabled: false }, pdfOnly)).toEqual({ perFile: 4_194_304, total: 4_194_304 });
    // Types the large flow cannot take keep the inline cap.
    const docx = "application/vnd.openxmlformats-officedocument.wordprocessingml.document";
    expect(effectiveCaps(LIMITS, [docx])).toEqual({ perFile: 4_194_304, total: 4_194_304 });
    expect(effectiveCaps(LIMITS, [])).toEqual({ perFile: 4_194_304, total: 4_194_304 });
    expect(FALLBACK_LIMITS.large_files_enabled).toBe(false);
  });

  it("fetches limits from GET /api/v1/tools without credentials and caches them", async () => {
    routes({ "GET /api/v1/tools": () => json({ items: [], limits: LIMITS }) });
    expect(await fetchLimits(BASE)).toEqual(LIMITS);
    expect(await fetchLimits(BASE)).toEqual(LIMITS);
    expect(fetchMock).toHaveBeenCalledOnce();
    expect(fetchMock.mock.calls[0]![1]?.credentials).toBe("omit");
  });

  it("resolves null (and retries later) when the catalog is unreachable", async () => {
    fetchMock.mockRejectedValueOnce(new TypeError("offline"));
    expect(await fetchLimits(BASE)).toBeNull();
    routes({ "GET /api/v1/tools": () => json({ items: [], limits: LIMITS }) });
    expect(await fetchLimits(BASE)).toEqual(LIMITS);
  });
});

describe("runInline", () => {
  it("posts multipart with files, options and consent and reads the filename", async () => {
    routes({
      "POST /api/v1/remove-pages": () =>
        new Response("PDF", {
          headers: { "Content-Type": "application/pdf", "Content-Disposition": 'attachment; filename="remove-pages-result.pdf"' },
        }),
    });
    const out = await runInline({ slug: "remove-pages", files: [pdf()], options: { pages: "1,3" }, aiConsent: false, baseUrl: BASE });
    expect(out.filename).toBe("remove-pages-result.pdf");
    expect(out.contentType).toBe("application/pdf");
    const body = fetchMock.mock.calls[0]![1]!.body as FormData;
    expect(body.getAll("files")).toHaveLength(1);
    expect(body.get("options")).toBe('{"pages":"1,3"}');
    expect(body.get("ai_consent")).toBe("false");
    expect(body.has("text")).toBe(false);
  });

  it("maps problem codes, 413 without a body, and network failures", async () => {
    routes({ "POST /api/v1/x": () => json({ code: "too_many_pages" }, 422, { "X-Request-Id": "req_1" }) });
    await expect(runInline({ slug: "x", files: [], options: {}, baseUrl: BASE })).rejects.toMatchObject({
      code: "too_many_pages",
      requestId: "req_1",
    });
    routes({ "POST /api/v1/x": () => new Response("<html>", { status: 413 }) });
    await expect(runInline({ slug: "x", files: [], options: {}, baseUrl: BASE })).rejects.toMatchObject({ code: "file_too_large" });
    fetchMock.mockRejectedValue(new TypeError("Failed to fetch"));
    await expect(runInline({ slug: "x", files: [], options: {}, baseUrl: BASE })).rejects.toMatchObject({ code: "network_error" });
  });
});

describe("createUpload", () => {
  it("declares size and content type per file", async () => {
    routes({
      "POST /api/v1/uploads": () =>
        json({ upload_id: UPLOAD_ID, expires_at: "2026-11-04T13:00:00Z", files: [{ index: 0, put_url: PUT_URL(0), headers: {} }] }, 201),
    });
    await createUpload("remove-pages", [new File(["x"], "scan.PDF", { type: "" })], { baseUrl: BASE, origins: ORIGINS });
    expect(JSON.parse(fetchMock.mock.calls[0]![1]!.body as string)).toEqual({
      tool: "remove-pages",
      files: [{ size: 1, content_type: "application/pdf" }],
    });
  });

  it("refuses types the large flow cannot take without calling the API", async () => {
    expect(uploadContentType({ name: "a.docx", type: "application/msword" })).toBeNull();
    await expect(createUpload("x", [new File(["x"], "a.docx")], { baseUrl: BASE, origins: ORIGINS })).rejects.toMatchObject({ code: "unsupported_type" });
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("maps 503 to large_files_unavailable and rejects malformed responses", async () => {
    routes({ "POST /api/v1/uploads": () => new Response(null, { status: 503 }) });
    await expect(createUpload("x", [pdf()], { baseUrl: BASE, origins: ORIGINS })).rejects.toMatchObject({ code: "large_files_unavailable" });
    routes({
      "POST /api/v1/uploads": () =>
        json({ upload_id: UPLOAD_ID, expires_at: "x", files: [{ index: 0, put_url: "javascript:alert(1)", headers: {} }] }, 201),
    });
    await expect(createUpload("x", [pdf()], { baseUrl: BASE, origins: ORIGINS })).rejects.toMatchObject({ code: "internal_error" });
  });

  it("drops (deletes) an upload whose put_url is off the storage allowlist, without echoing the URL", async () => {
    routes({
      "POST /api/v1/uploads": () =>
        json({ upload_id: UPLOAD_ID, expires_at: "x", files: [{ index: 0, put_url: "https://evil.test/x?signature=SECRET", headers: {} }] }, 201),
      [`DELETE /api/v1/uploads/${UPLOAD_ID}`]: () => new Response(null, { status: 204 }),
    });
    const error = await createUpload("x", [pdf()], { baseUrl: BASE, origins: ORIGINS }).catch((e: ToolRunError) => e);
    expect(error).toMatchObject({ code: "internal_error" });
    expect((error as Error).message).not.toContain("evil");
    await vi.waitFor(() => expect(fetchMock.mock.calls.some(([, init]) => init?.method === "DELETE")).toBe(true));
  });
});

describe("putFile", () => {
  it("PUTs the raw file with the signed headers except Content-Length, and reports progress", async () => {
    const progress = vi.fn();
    const file = pdf("a.pdf", 100);
    await putFile(
      {
        put_url: PUT_URL(0),
        headers: { "Content-Type": "application/pdf", "content-length": "100", "x-amz-meta": "1", "Content-MD5": "m", Authorization: "x", Host: "h" },
      },
      file,
      { onProgress: progress },
    );
    const xhr = FakeXHR.instances[0]!;
    expect(xhr.method).toBe("PUT");
    expect(xhr.url).toBe(PUT_URL(0));
    expect(xhr.headers).toEqual({ "Content-Type": "application/pdf", "x-amz-meta": "1", "Content-MD5": "m" });
    expect(xhr.body).toBe(file);
    expect(progress).toHaveBeenCalledWith(50, 100);
    expect(progress).toHaveBeenLastCalledWith(100, 100);
  });

  it("rejects with upload_failed on a storage error and cancelled on abort", async () => {
    FakeXHR.status = 403;
    await expect(putFile({ put_url: PUT_URL(0), headers: {} }, pdf())).rejects.toMatchObject({ code: "upload_failed" });
    FakeXHR.auto = false;
    const controller = new AbortController();
    const pending = putFile({ put_url: PUT_URL(0), headers: {} }, pdf(), { signal: controller.signal });
    controller.abort();
    await expect(pending).rejects.toMatchObject({ code: "cancelled" });
  });
});

describe("runLargeFlow", () => {
  const created = (n: number) =>
    json(
      {
        upload_id: UPLOAD_ID,
        expires_at: "2026-11-04T13:00:00Z",
        files: Array.from({ length: n }, (_, i) => ({ index: i, put_url: PUT_URL(i), headers: { "Content-Type": "application/pdf" } })),
      },
      201,
    );
  const result = {
    download_url: "https://storage.test/results/out?signature=SECRET",
    filename: "remove-pages-result.pdf",
    media_type: "application/pdf",
    size: 5,
    expires_at: "2026-11-04T12:30:00Z",
  };

  it("creates the upload, PUTs every file, runs the tool and returns the download URL", async () => {
    let runBody: unknown;
    routes({
      "POST /api/v1/uploads": () => created(2),
      [`POST /api/v1/uploads/${UPLOAD_ID}/run/merge-pdf`]: (init) => {
        runBody = JSON.parse(init!.body as string);
        return json(result);
      },
    });
    const stages: string[] = [];
    const progress = vi.fn();
    const onUploadCreated = vi.fn();
    const out = await runLargeFlow({
      slug: "merge-pdf",
      files: [pdf("a.pdf", 10), pdf("b.pdf", 20)],
      options: { keep_bookmarks: true },
      aiConsent: undefined,
      baseUrl: BASE,
      origins: ORIGINS,
      onStage: (s) => stages.push(s),
      onProgress: progress,
      onUploadCreated,
    });
    expect(out).toMatchObject({ uploadId: UPLOAD_ID, download_url: result.download_url, filename: result.filename });
    expect(onUploadCreated).toHaveBeenCalledWith(UPLOAD_ID);
    expect(FakeXHR.instances.map((x) => x.url)).toEqual([PUT_URL(0), PUT_URL(1)]);
    expect(stages).toEqual(["uploading", "processing"]);
    expect(progress).toHaveBeenLastCalledWith([1, 1]);
    expect(runBody).toEqual({ options: { keep_bookmarks: true } });
    // The caller deletes after starting the download.
    expect(fetchMock.mock.calls.some(([, init]) => init?.method === "DELETE")).toBe(false);
  });

  it("deletes the upload when the run fails, and surfaces the problem code", async () => {
    routes({
      "POST /api/v1/uploads": () => created(1),
      [`POST /api/v1/uploads/${UPLOAD_ID}/run/remove-pages`]: () => json({ code: "upload_incomplete" }, 409),
      [`DELETE /api/v1/uploads/${UPLOAD_ID}`]: () => new Response(null, { status: 204 }),
    });
    await expect(runLargeFlow({ slug: "remove-pages", files: [pdf()], options: {}, baseUrl: BASE, origins: ORIGINS })).rejects.toMatchObject({
      code: "upload_incomplete",
    });
    const del = fetchMock.mock.calls.find(([, init]) => init?.method === "DELETE");
    expect(del?.[1]).toMatchObject({ keepalive: true, credentials: "omit" });
  });

  it("deletes the upload when a PUT fails or the user cancels", async () => {
    routes({
      "POST /api/v1/uploads": () => created(1),
      [`DELETE /api/v1/uploads/${UPLOAD_ID}`]: () => new Response(null, { status: 204 }),
    });
    FakeXHR.status = 500;
    await expect(runLargeFlow({ slug: "x", files: [pdf()], options: {}, baseUrl: BASE, origins: ORIGINS })).rejects.toMatchObject({ code: "upload_failed" });
    expect(fetchMock.mock.calls.filter(([, init]) => init?.method === "DELETE")).toHaveLength(1);

    FakeXHR.auto = false;
    resetDeletedUploads(); // same id reused by the fake API
    const controller = new AbortController();
    const pending = runLargeFlow({ slug: "x", files: [pdf()], options: {}, baseUrl: BASE, origins: ORIGINS, signal: controller.signal });
    await vi.waitFor(() => expect(FakeXHR.instances).toHaveLength(2));
    controller.abort();
    await expect(pending).rejects.toMatchObject({ code: "cancelled" });
    expect(fetchMock.mock.calls.filter(([, init]) => init?.method === "DELETE")).toHaveLength(2);
  });

  it("refuses a download URL on an unknown origin", async () => {
    routes({
      "POST /api/v1/uploads": () => created(1),
      [`POST /api/v1/uploads/${UPLOAD_ID}/run/x`]: () => json({ ...result, download_url: "https://evil.test/out" }),
      [`DELETE /api/v1/uploads/${UPLOAD_ID}`]: () => new Response(null, { status: 204 }),
    });
    await expect(runLargeFlow({ slug: "x", files: [pdf()], options: {}, baseUrl: BASE, origins: ORIGINS })).rejects.toMatchObject({
      code: "internal_error",
    });
  });

  it("refuses a non-http download URL", async () => {
    routes({
      "POST /api/v1/uploads": () => created(1),
      [`POST /api/v1/uploads/${UPLOAD_ID}/run/x`]: () => json({ ...result, download_url: "javascript:alert(1)" }),
      [`DELETE /api/v1/uploads/${UPLOAD_ID}`]: () => new Response(null, { status: 204 }),
    });
    await expect(runLargeFlow({ slug: "x", files: [pdf()], options: {}, baseUrl: BASE, origins: ORIGINS })).rejects.toBeInstanceOf(ToolRunError);
  });

  it("never logs presigned URLs", async () => {
    const spies = (["log", "info", "warn", "error", "debug"] as const).map((m) => vi.spyOn(console, m));
    routes({
      "POST /api/v1/uploads": () => created(1),
      [`POST /api/v1/uploads/${UPLOAD_ID}/run/x`]: () => json({ code: "processing_failed" }, 422),
      [`DELETE /api/v1/uploads/${UPLOAD_ID}`]: () => new Response(null, { status: 204 }),
    });
    await runLargeFlow({ slug: "x", files: [pdf()], options: {}, baseUrl: BASE, origins: ORIGINS }).catch((e: ToolRunError) => {
      expect(e.message).not.toContain("SECRET");
    });
    for (const spy of spies) expect(spy).not.toHaveBeenCalled();
  });
});

describe("deleteUpload", () => {
  it("sends DELETE with keepalive, at most once per id", async () => {
    fetchMock.mockResolvedValue(new Response(null, { status: 204 }));
    await deleteUpload(UPLOAD_ID, { baseUrl: BASE });
    await deleteUpload(UPLOAD_ID, { baseUrl: BASE });
    expect(fetchMock).toHaveBeenCalledOnce();
    expect(fetchMock).toHaveBeenCalledWith(`${BASE}/api/v1/uploads/${UPLOAD_ID}`, {
      method: "DELETE",
      credentials: "omit",
      keepalive: true,
    });
  });

  it("retries transient failures with backoff, but not while unloading", async () => {
    vi.useFakeTimers();
    try {
      fetchMock
        .mockRejectedValueOnce(new TypeError("offline"))
        .mockResolvedValueOnce(new Response(null, { status: 503 }))
        .mockResolvedValueOnce(new Response(null, { status: 204 }));
      const done = deleteUpload(UPLOAD_ID, { baseUrl: BASE });
      await vi.runAllTimersAsync();
      await expect(done).resolves.toBeUndefined();
      expect(fetchMock).toHaveBeenCalledTimes(3);

      fetchMock.mockReset();
      fetchMock.mockRejectedValue(new TypeError("offline"));
      const other = "u_" + "b".repeat(32);
      const unload = deleteUpload(other, { baseUrl: BASE, unloading: true });
      await vi.runAllTimersAsync();
      await unload;
      expect(fetchMock).toHaveBeenCalledOnce();
    } finally {
      vi.useRealTimers();
    }
  });

  it("does not retry a 4xx and ignores malformed ids", async () => {
    fetchMock.mockResolvedValue(new Response(null, { status: 400 }));
    await deleteUpload(UPLOAD_ID, { baseUrl: BASE });
    expect(fetchMock).toHaveBeenCalledOnce();
    await deleteUpload("../../etc", { baseUrl: BASE });
    expect(fetchMock).toHaveBeenCalledOnce();
  });
});

describe("trusted URLs and file names", () => {
  it("accepts only allowlisted http(s) origins", () => {
    expect(isTrustedUrl("https://storage.test/a?x=1", ["https://storage.test"])).toBe(true);
    expect(isTrustedUrl("https://storage.test.evil.com/a", ["https://storage.test"])).toBe(false);
    expect(isTrustedUrl("javascript:alert(1)", ["https://storage.test"])).toBe(false);
    expect(isTrustedUrl("not a url", ["https://storage.test"])).toBe(false);
  });

  it("derives a safe download name from the original file name", () => {
    expect(derivedFilename("My report (v2).pdf", "-removed", "pdf")).toBe("My report (v2)-removed.pdf");
    expect(derivedFilename("../../etc/passwd", "-removed", "pdf")).toBe("etc_passwd-removed.pdf");
    expect(derivedFilename('a<b>:"c".PDF', "-removed", "pdf")).toBe("a_b_c-removed.pdf");
    expect(derivedFilename(".pdf", "-removed", "pdf")).toBe("document-removed.pdf");
  });
});
