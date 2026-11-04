import { act, renderHook, waitFor } from "@testing-library/react";
import { StrictMode, type ReactNode } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("@/lib/env", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/lib/env")>()),
  uploadOrigins: ["https://storage.test"],
}));
const triggerDownload = vi.fn();
vi.mock("@/lib/api/uploads", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/lib/api/uploads")>()),
  triggerDownload: (...args: unknown[]) => triggerDownload(...args),
}));

const { DOWNLOAD_GRACE_MS, useToolRunner } = await import("@/hooks/useToolRunner");
const { resetDeletedUploads } = await import("@/lib/api/uploads");
type Limits = import("@/lib/api/uploads").ApiLimits;

const UPLOAD_ID = "u_Zk3p9Qx1Lm7Rt5Vb2Nc8Hd4Jf6Sg0Wa";
const LARGE: Limits = {
  max_request_bytes: 1,
  max_pages: 500,
  large_files_enabled: true,
  max_large_file_bytes: 1_000_000,
  max_large_total_bytes: 1_000_000,
  inline_max_bytes: 5,
};
const pdf = () => new File([new Uint8Array(20)], "a.pdf", { type: "application/pdf" });
const input = { files: [pdf()], options: { pages: "1" } };

class FakeXHR {
  static auto = true;
  static last: FakeXHR | null = null;
  upload: { onprogress: ((e: { loaded: number; total: number; lengthComputable: boolean }) => void) | null } = { onprogress: null };
  status = 0;
  onload: (() => void) | null = null;
  onerror: (() => void) | null = null;
  onabort: (() => void) | null = null;
  ontimeout: (() => void) | null = null;
  open() {
    FakeXHR.last = this;
  }
  setRequestHeader() {}
  send() {
    if (FakeXHR.auto) queueMicrotask(() => this.finish());
  }
  finish() {
    this.status = 200;
    this.onload?.();
  }
  abort() {
    this.onabort?.();
  }
}

let fetchMock: ReturnType<typeof vi.fn<(url: string, init?: RequestInit) => Promise<Response>>>;
let runStatus = 200;

const deletes = () => fetchMock.mock.calls.filter(([, init]) => init?.method === "DELETE");
const creates = () => fetchMock.mock.calls.filter(([url]) => url.endsWith("/api/v1/uploads"));

beforeEach(() => {
  FakeXHR.auto = true;
  runStatus = 200;
  triggerDownload.mockReset();
  resetDeletedUploads();
  vi.stubGlobal("XMLHttpRequest", FakeXHR);
  URL.createObjectURL = vi.fn(() => "blob:x");
  URL.revokeObjectURL = vi.fn();
  fetchMock = vi.fn<(url: string, init?: RequestInit) => Promise<Response>>(async (url, init) => {
    const path = new URL(url).pathname;
    if (init?.method === "DELETE") return new Response(null, { status: 204 });
    if (path === "/api/v1/uploads") {
      return new Response(
        JSON.stringify({
          upload_id: UPLOAD_ID,
          expires_at: "2026-11-04T13:00:00Z",
          files: [{ index: 0, put_url: "https://storage.test/in?signature=S", headers: { "Content-Type": "application/pdf" } }],
        }),
        { status: 201 },
      );
    }
    if (path.endsWith("/run/remove-pages")) {
      if (runStatus !== 200) return new Response(JSON.stringify({ code: "upload_incomplete" }), { status: runStatus });
      return new Response(
        JSON.stringify({
          download_url: "https://storage.test/out?signature=S",
          filename: "remove-pages-result.pdf",
          media_type: "application/pdf",
          size: 5,
          expires_at: "2026-11-04T13:00:00Z",
        }),
      );
    }
    throw new Error(`unexpected ${path}`);
  });
  vi.stubGlobal("fetch", fetchMock);
});

afterEach(() => {
  vi.useRealTimers();
  vi.unstubAllGlobals();
});

function setup(wrapper?: (props: { children: ReactNode }) => ReactNode) {
  return renderHook(() => useToolRunner("remove-pages", LARGE), { wrapper });
}

describe("useToolRunner (large-file flow)", () => {
  it("downloads on success and deletes the upload exactly once on unmount", async () => {
    const { result, unmount } = setup();
    await act(() => result.current.run(input));
    expect(result.current.state).toMatchObject({ phase: "succeeded", filename: "remove-pages-result.pdf" });
    expect(triggerDownload).toHaveBeenCalledWith("https://storage.test/out?signature=S", "remove-pages-result.pdf");
    expect(deletes()).toHaveLength(0);
    unmount();
    expect(deletes()).toHaveLength(1);
    expect(deletes()[0]![1]).toMatchObject({ keepalive: true });
  });

  it("keeps a large-file result for 5 minutes at most", () => {
    expect(DOWNLOAD_GRACE_MS).toBe(300_000);
  });

  it("deletes after the grace period and marks the result expired", async () => {
    vi.useFakeTimers({ toFake: ["setTimeout", "clearTimeout"] });
    const { result, unmount } = setup();
    await act(() => result.current.run(input));
    act(() => {
      vi.advanceTimersByTime(DOWNLOAD_GRACE_MS - 1);
    });
    expect(deletes()).toHaveLength(0);
    act(() => {
      vi.advanceTimersByTime(1);
    });
    expect(deletes()).toHaveLength(1);
    expect(result.current.state).toMatchObject({ phase: "succeeded", expired: true });
    unmount();
    expect(deletes()).toHaveLength(1);
  });

  it("clears the grace timer on unmount (one DELETE, no late one)", async () => {
    vi.useFakeTimers({ toFake: ["setTimeout", "clearTimeout"] });
    const { result, unmount } = setup();
    await act(() => result.current.run(input));
    unmount();
    expect(deletes()).toHaveLength(1);
    vi.advanceTimersByTime(DOWNLOAD_GRACE_MS * 2);
    expect(deletes()).toHaveLength(1);
  });

  it("cancel during upload returns to idle and deletes once", async () => {
    FakeXHR.auto = false;
    const { result } = setup();
    let pending!: Promise<void>;
    act(() => {
      pending = result.current.run(input);
    });
    await waitFor(() => expect(FakeXHR.last).not.toBeNull());
    expect(result.current.cancellable).toBe(true);
    await act(async () => {
      result.current.cancel();
      await pending;
    });
    expect(result.current.state).toEqual({ phase: "idle" });
    expect(deletes()).toHaveLength(1);
  });

  it("reset after success deletes once and clears the result", async () => {
    const { result, unmount } = setup();
    await act(() => result.current.run(input));
    act(() => result.current.reset());
    expect(result.current.result).toBeNull();
    expect(result.current.state).toEqual({ phase: "idle" });
    unmount();
    expect(deletes()).toHaveLength(1);
  });

  it("ignores a second run while one is in flight", async () => {
    FakeXHR.auto = false;
    FakeXHR.last = null;
    const { result } = setup();
    let first!: Promise<void>;
    act(() => {
      first = result.current.run(input);
      void result.current.run(input);
    });
    await waitFor(() => expect(FakeXHR.last).not.toBeNull());
    await act(async () => {
      FakeXHR.last!.finish();
      await first;
    });
    expect(creates()).toHaveLength(1);
    expect(result.current.state.phase).toBe("succeeded");
  });

  it("pagehide aborts the job and deletes with keepalive; a bfcache restore shows idle", async () => {
    FakeXHR.auto = false;
    FakeXHR.last = null;
    const { result } = setup();
    let pending!: Promise<void>;
    act(() => {
      pending = result.current.run(input);
    });
    await waitFor(() => expect(FakeXHR.last).not.toBeNull());
    await act(async () => {
      window.dispatchEvent(new Event("pagehide"));
      await pending;
    });
    expect(deletes()).toHaveLength(1);
    expect(deletes()[0]![1]).toMatchObject({ keepalive: true });
    act(() => {
      const show = new Event("pageshow") as PageTransitionEvent;
      Object.defineProperty(show, "persisted", { value: true });
      window.dispatchEvent(show);
    });
    expect(result.current.state).toEqual({ phase: "idle" });
  });

  it("works under StrictMode double-mount", async () => {
    const { result, unmount } = setup(({ children }) => <StrictMode>{children}</StrictMode>);
    await act(() => result.current.run(input));
    expect(result.current.state.phase).toBe("succeeded");
    expect(deletes()).toHaveLength(0);
    unmount();
    expect(deletes()).toHaveLength(1);
  });

  it("a failure inside the flow deletes the upload exactly once", async () => {
    runStatus = 409;
    const { result, unmount } = setup();
    await act(() => result.current.run(input));
    expect(result.current.state).toMatchObject({ phase: "failed", errorCode: "upload_incomplete" });
    unmount();
    expect(deletes()).toHaveLength(1);
  });

  it("a failure after the flow returned (e.g. download) deletes exactly once", async () => {
    triggerDownload.mockImplementation(() => {
      throw new Error("blocked");
    });
    const { result, unmount } = setup();
    await act(() => result.current.run(input));
    expect(result.current.state).toMatchObject({ phase: "failed", errorCode: "internal_error" });
    expect(deletes()).toHaveLength(1);
    unmount();
    expect(deletes()).toHaveLength(1);
  });
});
