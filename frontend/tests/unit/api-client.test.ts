import { afterEach, describe, expect, it, vi } from "vitest";
import { createApiClient } from "@/lib/api/client";
import { errorMessage } from "@/lib/api/errors";
import { parseBaseUrl, resolveApiBaseUrl } from "@/lib/env";

function mockFetch() {
  const fetchMock = vi.fn<(request: Request) => Promise<Response>>(async () =>
    new Response(JSON.stringify({ ok: true }), { status: 200, headers: { "Content-Type": "application/json" } }),
  );
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

describe("api client", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("calls the configured base URL with credentials included", async () => {
    const fetchMock = mockFetch();
    const client = createApiClient("http://api.test");
    await client.GET("/api/v1/tools");
    const request = fetchMock.mock.calls[0]![0];
    expect(request.url).toBe("http://api.test/api/v1/tools");
    expect(request.credentials).toBe("include");
  });

  it("maps error codes to messages", () => {
    expect(errorMessage("file_too_large")).toMatch(/larger than allowed/);
    expect(errorMessage(undefined)).toMatch(/Something went wrong/);
  });
});

describe("API base URL", () => {
  it("strips trailing slashes and falls back to localhost outside production", () => {
    expect(resolveApiBaseUrl({ NEXT_PUBLIC_API_BASE_URL: "https://api.example.com/" }, false)).toBe(
      "https://api.example.com",
    );
    expect(resolveApiBaseUrl({}, false)).toBe("http://localhost:8000");
  });

  it("fails production builds when the URL is missing", () => {
    expect(() => resolveApiBaseUrl({}, true)).toThrow();
  });

  it("rejects non-http URLs", () => {
    expect(() => parseBaseUrl("javascript:alert(1)", "X")).toThrow();
    expect(() => parseBaseUrl("not a url", "X")).toThrow();
  });
});
