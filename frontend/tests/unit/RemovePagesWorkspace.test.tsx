import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { useToolRunner } from "@/hooks/useToolRunner";

const openPdf = vi.fn();
vi.mock("@/lib/pdf/thumbnails", () => ({
  openPdf: (...args: unknown[]) => openPdf(...args),
  closePdf: () => Promise.resolve(),
  renderThumbnail: () => Promise.resolve({ url: "blob:thumb", aspect: 0.7 }),
  PdfOpenError: class PdfOpenError extends Error {
    reason: string;
    constructor(reason: string) {
      super(reason);
      this.reason = reason;
    }
  },
}));

const { RemovePagesWorkspace } = await import("@/components/tools/remove-pages/RemovePagesWorkspace");
const { PdfOpenError } = await import("@/lib/pdf/thumbnails");

type Runner = ReturnType<typeof useToolRunner>;

function makeRunner(overrides: Partial<Runner> = {}): Runner {
  return {
    state: { phase: "idle" },
    result: null,
    busy: false,
    cancellable: false,
    run: vi.fn(async () => undefined),
    cancel: vi.fn(),
    reset: vi.fn(),
    download: vi.fn(),
    ...overrides,
  };
}

const file = new File(["%PDF-1.7"], "report.pdf", { type: "application/pdf" });

async function setup(runner = makeRunner(), pages = 10) {
  openPdf.mockResolvedValue({ numPages: pages });
  const onChangeFile = vi.fn();
  render(<RemovePagesWorkspace file={file} runner={runner} onChangeFile={onChangeFile} />);
  await screen.findByRole("list", { name: "Pages" });
  const input = screen.getByLabelText("Pages to remove") as HTMLInputElement;
  const page = (n: number) => screen.getByRole("button", { name: `Page ${n}` });
  // [0] is the panel CTA (lg+), [1] the small-screen action bar; CSS picks one, jsdom has both.
  const cta = (screen.queryAllByRole("button", { name: "Remove pages" })[0] ?? null) as HTMLButtonElement;
  return { runner, onChangeFile, input, page, cta };
}

beforeEach(() => {
  openPdf.mockReset();
});

describe("RemovePagesWorkspace", () => {
  it("renders one toggle button per page and the page total", async () => {
    await setup();
    const grid = screen.getByRole("list", { name: "Pages" });
    expect(within(grid).getAllByRole("button")).toHaveLength(10);
    expect(screen.getByText("Total pages:").parentElement).toHaveTextContent("Total pages: 10");
    expect(screen.getByRole("button", { name: "Page 1" })).toHaveAttribute("aria-pressed", "false");
  });

  it("click toggles a page and rewrites the input; shift+click selects a range", async () => {
    const user = userEvent.setup();
    const { input, page, cta } = await setup();
    expect(cta).toBeDisabled();
    await user.click(page(2));
    expect(page(2)).toHaveAttribute("aria-pressed", "true");
    expect(input.value).toBe("2");
    await user.keyboard("{Shift>}");
    await user.click(page(5));
    await user.keyboard("{/Shift}");
    expect(input.value).toBe("2-5");
    expect(screen.getByText(/selected, 6 will remain/)).toHaveTextContent("4 pages selected, 6 will remain.");
    await user.click(page(9));
    expect(input.value).toBe("2-5, 9");
    await user.click(page(3));
    expect(input.value).toBe("2, 4-5, 9");
    expect(cta).toBeEnabled();
  });

  it("typing updates the grid live, including reversed ranges", async () => {
    const user = userEvent.setup();
    const { input, page } = await setup();
    await user.type(input, "1, 8-6");
    for (const n of [1, 6, 7, 8]) expect(page(n)).toHaveAttribute("aria-pressed", "true");
    expect(page(2)).toHaveAttribute("aria-pressed", "false");
    await user.tab();
    expect(input.value).toBe("1, 6-8");
  });

  it("explains ignored and unreadable parts", async () => {
    const user = userEvent.setup();
    const { input, page } = await setup();
    await user.type(input, "3, 12");
    expect(screen.getByText(/Ignored, the document has 10 pages: 12/)).toBeInTheDocument();
    expect(page(3)).toHaveAttribute("aria-pressed", "true");
    await user.clear(input);
    await user.type(input, "abc");
    expect(screen.getByText(/Not understood: abc/)).toBeInTheDocument();
    expect(input).toHaveAttribute("aria-invalid", "true");
  });

  it("refuses to remove every page", async () => {
    const user = userEvent.setup();
    const { input, cta } = await setup();
    await user.type(input, "1-10");
    expect(screen.getByText("You can't remove every page.")).toBeInTheDocument();
    expect(cta).toBeDisabled();
  });

  it("makes the grid a single tab stop with arrow, Home/End and Shift range keys", async () => {
    const user = userEvent.setup();
    const { input, page } = await setup();
    const grid = screen.getByRole("list", { name: "Pages" });
    expect(within(grid).getAllByRole("button").filter((b) => b.tabIndex === 0)).toEqual([page(1)]);
    page(1).focus();
    await user.keyboard("{ArrowRight}{ArrowRight}{ArrowRight}");
    expect(page(4)).toHaveFocus();
    expect(page(4)).toHaveAttribute("tabindex", "0");
    expect(page(1)).toHaveAttribute("tabindex", "-1");
    await user.keyboard("{Enter}");
    expect(input.value).toBe("4");
    await user.keyboard("{Shift>}{ArrowRight}{ArrowRight}{/Shift}");
    expect(page(6)).toHaveFocus();
    expect(input.value).toBe("4-6");
    await user.keyboard(" ");
    expect(input.value).toBe("4-5");
    await user.keyboard("{End}");
    expect(page(10)).toHaveFocus();
    // The anchor is the last toggled page (6), so the range runs 6-10.
    await user.keyboard("{Shift>}{Enter}{/Shift}");
    expect(input.value).toBe("4-10");
    await user.keyboard("{Home}{ArrowLeft}");
    expect(page(1)).toHaveFocus();
  });

  it("offers a skip link to the page field", async () => {
    const user = userEvent.setup();
    const { input } = await setup();
    await user.click(screen.getByRole("link", { name: "Skip to Pages to remove" }));
    expect(input).toHaveFocus();
  });

  it("disables Remove while the field has unreadable parts", async () => {
    const user = userEvent.setup();
    const { input, cta } = await setup();
    await user.type(input, "2, x");
    expect(screen.getByRole("button", { name: "Page 2" })).toHaveAttribute("aria-pressed", "true");
    expect(cta).toBeDisabled();
    expect(screen.getByText(/Not understood: x/)).toBeInTheDocument();
  });

  it("small-screen bar shows the counts, removes, and jumps to the field", async () => {
    const user = userEvent.setup();
    const { runner, input, page } = await setup();
    const bar = screen.getByTestId("mobile-action-bar");
    await user.click(page(3));
    expect(bar).toHaveTextContent("1 selected · 9 remain");
    await user.click(within(bar).getByRole("button", { name: "Type pages" }));
    expect(input).toHaveFocus();
    await user.click(within(bar).getByRole("button", { name: "Remove pages" }));
    expect(runner.run).toHaveBeenCalledOnce();
  });

  it("small-screen bar shows upload progress and Cancel while uploading, then refocuses Remove", async () => {
    const user = userEvent.setup();
    const idle = makeRunner();
    openPdf.mockResolvedValue({ numPages: 10 });
    const view = (runner: Runner) => <RemovePagesWorkspace file={file} runner={runner} onChangeFile={vi.fn()} />;
    const { rerender } = render(view(idle));
    await screen.findByRole("list", { name: "Pages" });
    await user.click(screen.getByRole("button", { name: "Page 2" }));

    const uploading = makeRunner({ state: { phase: "uploading", progress: [0.42] }, busy: true, cancellable: true });
    rerender(view(uploading));
    const bar = screen.getByTestId("mobile-action-bar");
    expect(bar).toHaveTextContent("Uploading 42%");
    expect(within(bar).getByRole("progressbar")).toHaveAttribute("aria-valuenow", "42");
    // The panel's copy is display:none below lg (one progressbar for assistive tech).
    expect(screen.getAllByRole("progressbar")[0]!.closest(".hidden")).not.toBeNull();
    expect(within(bar).queryByRole("button", { name: /Remove pages|Uploading/ })).not.toBeInTheDocument();
    const cancel = within(bar).getByRole("button", { name: "Cancel" });
    expect(cancel.className).toContain("min-h-11");
    await user.click(cancel);
    expect(uploading.cancel).toHaveBeenCalled();

    // The runner goes idle; focus lands on a Remove control, not <body>.
    rerender(view(idle));
    expect(document.activeElement).not.toBe(document.body);
    expect(document.activeElement).toHaveTextContent("Remove pages");
  });

  it("small-screen bar shows Processing… while processing", async () => {
    const runner = makeRunner({ state: { phase: "processing" }, busy: true });
    openPdf.mockResolvedValue({ numPages: 10 });
    render(<RemovePagesWorkspace file={file} runner={runner} onChangeFile={vi.fn()} />);
    await screen.findByRole("list", { name: "Pages" });
    expect(screen.getByTestId("mobile-action-bar")).toHaveTextContent("Processing…");
  });

  it("keeps focus on the CTA while busy (aria-disabled, click ignored)", async () => {
    const user = userEvent.setup();
    const runner = makeRunner({ state: { phase: "processing" }, busy: true });
    openPdf.mockResolvedValue({ numPages: 10 });
    render(<RemovePagesWorkspace file={file} runner={runner} onChangeFile={vi.fn()} />);
    await screen.findByRole("list", { name: "Pages" });
    const cta = screen.getAllByRole("button", { name: "Removing…" })[0]!;
    expect(cta).toHaveAttribute("aria-disabled", "true");
    await user.click(cta);
    expect(runner.run).not.toHaveBeenCalled();
  });

  it("on failure the CTA retries and the panel action dismisses", async () => {
    const user = userEvent.setup();
    const runner = makeRunner({ state: { phase: "failed", errorCode: "processing_failed" } });
    const { input } = await setup(runner);
    expect(screen.getByRole("alert")).toHaveTextContent(/could not process/);
    expect(screen.getByRole("alert")).toHaveFocus();
    await user.type(input, "2");
    await user.click(screen.getAllByRole("button", { name: "Try again" })[0]!);
    expect(runner.run).toHaveBeenCalledOnce();
    await user.click(screen.getByRole("button", { name: "Dismiss" }));
    expect(runner.reset).toHaveBeenCalled();
  });

  it("clear selection empties both the grid and the input", async () => {
    const user = userEvent.setup();
    const { input, page } = await setup();
    await user.click(page(1));
    await user.click(screen.getByRole("button", { name: "Clear selection" }));
    expect(input.value).toBe("");
    expect(page(1)).toHaveAttribute("aria-pressed", "false");
  });

  it("sends the backend `pages` option and offers to remove more after success", async () => {
    const user = userEvent.setup();
    const { runner, input, cta } = await setup();
    await user.type(input, "8-5, 1");
    await user.click(cta);
    expect(runner.run).toHaveBeenCalledWith({
      files: [file],
      options: { pages: "1,5-8" },
      downloadName: "report-removed.pdf",
    });
  });

  it("shows the result actions when done", async () => {
    const user = userEvent.setup();
    const runner = makeRunner({
      state: { phase: "succeeded", filename: "out.pdf" },
      result: { url: "blob:out", filename: "report-removed.pdf", remote: false },
    });
    const { onChangeFile, cta, page } = await setup(runner);
    expect(cta).toBeNull();
    expect(page(1)).toBeDisabled();
    // The small-screen bar stays, with the result actions.
    const bar = screen.getByTestId("mobile-action-bar");
    expect(bar).toHaveTextContent("Result ready");
    const barDownload = within(bar).getByRole("button", { name: "Download result" });
    expect(barDownload.className).toContain("min-h-12");
    // Focus lands on a Download button (jsdom has no layout, so the bar's is chosen).
    expect(barDownload).toHaveFocus();
    await user.click(barDownload);
    expect(runner.download).toHaveBeenCalledOnce();
    await user.click(within(bar).getByRole("button", { name: "Remove more pages" }));
    expect(runner.reset).toHaveBeenCalled();
    await user.click(within(bar).getByRole("button", { name: "Start over" }));
    expect(onChangeFile).toHaveBeenCalled();
    // The panel keeps the same actions for lg+.
    const panel = screen.getByRole("complementary", { name: "Remove pages options" });
    expect(within(panel).getByRole("button", { name: "Download result" })).toBeInTheDocument();
    expect(within(panel).getByRole("button", { name: "Start over" })).toBeInTheDocument();
  });

  it("explains password-protected files", async () => {
    openPdf.mockRejectedValue(new PdfOpenError("password"));
    render(<RemovePagesWorkspace file={file} runner={makeRunner()} onChangeFile={vi.fn()} />);
    expect(await screen.findByText("This PDF is password protected")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Choose another file" })).toBeInTheDocument();
  });
});
