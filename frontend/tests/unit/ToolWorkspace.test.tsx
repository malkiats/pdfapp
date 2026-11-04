import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ToolWorkspace } from "@/components/tools/ToolWorkspace";
import { resetLimitsCache, type ApiLimits } from "@/lib/api/uploads";

const MB = 1024 * 1024;
const base = {
  toolSlug: "merge-pdf",
  title: "Merge PDF",
  inputKinds: ["file" as const],
  accepts: ["application/pdf"],
  minInputs: 2,
  maxInputs: 5,
  maxFileBytes: 500 * MB,
  requiresAiConsent: false,
};

const LARGE: ApiLimits = {
  max_request_bytes: 26_214_400,
  max_pages: 500,
  large_files_enabled: true,
  max_large_file_bytes: 100 * MB,
  max_large_total_bytes: 200 * MB,
  inline_max_bytes: 4 * MB,
};

let fetchMock: ReturnType<typeof vi.fn<(url: string, init?: RequestInit) => Promise<Response>>>;

function serveLimits(limits: ApiLimits | null) {
  fetchMock.mockImplementation(async (url) => {
    if (url.endsWith("/api/v1/tools") && limits) {
      return new Response(JSON.stringify({ items: [], limits }), { headers: { "Content-Type": "application/json" } });
    }
    throw new TypeError("offline");
  });
}

beforeEach(() => {
  resetLimitsCache();
  fetchMock = vi.fn<(url: string, init?: RequestInit) => Promise<Response>>();
  vi.stubGlobal("fetch", fetchMock);
  serveLimits(null);
});

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("ToolWorkspace", () => {
  it("disables every input and labels the tool as coming soon", () => {
    render(<ToolWorkspace {...base} status="coming_soon" />);
    expect(screen.getByText(/coming soon/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Choose files" })).toBeDisabled();
    expect(screen.getByRole("status")).toBeInTheDocument();
  });

  it("enables the dropzone when the tool is available", () => {
    render(<ToolWorkspace {...base} status="available" />);
    expect(screen.queryByText(/Coming soon/)).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Choose files" })).toBeEnabled();
  });

  it("renders URL inputs and AI consent for URL/AI tools", () => {
    render(
      <ToolWorkspace
        {...base}
        title="Compare webpages"
        inputKinds={["url"]}
        accepts={[]}
        maxInputs={2}
        requiresAiConsent
        status="coming_soon"
      />,
    );
    expect(screen.getByLabelText("First page URL")).toBeDisabled();
    expect(screen.getByLabelText("Second page URL")).toBeDisabled();
    expect(screen.getByRole("checkbox", { name: /AI provider/ })).toBeDisabled();
    expect(screen.queryByRole("button", { name: "Choose files" })).not.toBeInTheDocument();
  });

  it("says it is checking limits, then falls back to the inline limit when the catalog is unreachable", async () => {
    render(<ToolWorkspace {...base} status="available" />);
    expect(screen.getByText(/checking size limits/)).toBeInTheDocument();
    expect(await screen.findByText(/up to 4\.2 MB each/)).toBeInTheDocument();
  });

  it("re-checks files picked before the limits arrived instead of rejecting them early", async () => {
    const user = userEvent.setup();
    let resolveLimits!: (r: Response) => void;
    fetchMock.mockImplementation(() => new Promise<Response>((r) => (resolveLimits = r)));
    render(<ToolWorkspace {...base} status="available" />);
    const big = new File(["x"], "big.pdf", { type: "application/pdf" });
    Object.defineProperty(big, "size", { value: 50 * MB });
    await user.upload(screen.getByTestId("file-input"), [big]);
    // Accepted while limits load (no early rejection against the 4 MB fallback).
    expect(screen.getByRole("list", { name: "Selected files" })).toHaveTextContent("big.pdf");
    resolveLimits(new Response(JSON.stringify({ items: [], limits: { ...LARGE, max_large_file_bytes: 10 * MB } })));
    // The real cap is lower: the file is now reported as rejected.
    expect(await screen.findByRole("alert")).toHaveTextContent("big.pdf: larger than 10 MB");
    expect(screen.queryByRole("list", { name: "Selected files" })).not.toBeInTheDocument();
  });

  it("shows and enforces the large-file limit when large files are enabled", async () => {
    serveLimits(LARGE);
    render(<ToolWorkspace {...base} status="available" />);
    expect(await screen.findByText(/up to 100 MB each/)).toBeInTheDocument();
    expect(fetchMock.mock.calls[0]![0]).toMatch(/\/api\/v1\/tools$/);
  });

  it("routes file sets above inline_max_bytes through the upload flow", async () => {
    const user = userEvent.setup();
    serveLimits({ ...LARGE, inline_max_bytes: 10 });
    render(<ToolWorkspace {...base} status="available" />);
    await screen.findByText(/up to 100 MB each/);

    fetchMock.mockImplementation(async (url, init) => {
      if (url.endsWith("/api/v1/uploads") && init?.method === "POST") {
        return new Response(JSON.stringify({ code: "large_files_unavailable" }), { status: 503 });
      }
      return new Response(null, { status: 204 });
    });
    const files = [new File([new Uint8Array(50)], "a.pdf", { type: "application/pdf" }), new File([new Uint8Array(50)], "b.pdf", { type: "application/pdf" })];
    await user.upload(screen.getByTestId("file-input"), files);
    await user.click(screen.getByRole("button", { name: "Merge PDF" }));

    expect(await screen.findByText(/Large files cannot be processed right now/)).toBeInTheDocument();
    const create = fetchMock.mock.calls.find(([url]) => url.endsWith("/api/v1/uploads"));
    expect(JSON.parse(create![1]!.body as string)).toMatchObject({ tool: "merge-pdf", files: [{ size: 50 }, { size: 50 }] });
    // No inline POST was made.
    expect(fetchMock.mock.calls.some(([url]) => url.endsWith("/api/v1/merge-pdf"))).toBe(false);
  });

  it("keeps small file sets on the inline multipart POST", async () => {
    const user = userEvent.setup();
    serveLimits(LARGE);
    render(<ToolWorkspace {...base} status="available" />);
    await screen.findByText(/up to 100 MB each/);
    fetchMock.mockResolvedValue(new Response(JSON.stringify({ code: "invalid_file" }), { status: 422 }));
    await user.upload(screen.getByTestId("file-input"), [
      new File(["%PDF"], "a.pdf", { type: "application/pdf" }),
      new File(["%PDF"], "b.pdf", { type: "application/pdf" }),
    ]);
    await user.click(screen.getByRole("button", { name: "Merge PDF" }));
    await waitFor(() => expect(screen.getByText(/damaged/)).toBeInTheDocument());
    const [url, init] = fetchMock.mock.calls.at(-1)!;
    expect(url).toMatch(/\/api\/v1\/merge-pdf$/);
    expect(init?.body).toBeInstanceOf(FormData);
  });

  it("replaces the generic options form for remove-pages", () => {
    render(<ToolWorkspace {...base} toolSlug="remove-pages" title="Remove pages" minInputs={1} maxInputs={1} status="available" />);
    expect(screen.queryByLabelText(/Pages to remove/)).not.toBeInTheDocument();
    expect(screen.getByText(/Add a PDF to see its pages/)).toBeInTheDocument();
  });
});
