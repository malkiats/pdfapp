import { render, renderHook, screen, waitFor } from "@testing-library/react";
import { useCallback } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const renderThumbnail = vi.fn(async (_doc: unknown, page: number) => ({ url: `blob:page-${page}`, aspect: 0.7 }));
const openPdf = vi.fn();
vi.mock("@/lib/pdf/thumbnails", () => ({
  openPdf: (...args: unknown[]) => openPdf(...args),
  closePdf: () => Promise.resolve(),
  renderThumbnail: (doc: unknown, page: number) => renderThumbnail(doc, page),
  PdfOpenError: class extends Error {},
}));

const { usePdfDocument, usePdfThumbnails } = await import("@/components/tools/remove-pages/usePdfThumbnails");

/** Reports every observed element as visible. */
class VisibleObserver {
  constructor(private readonly callback: IntersectionObserverCallback) {}
  observe(el: Element) {
    queueMicrotask(() =>
      this.callback([{ target: el, isIntersecting: true } as IntersectionObserverEntry], this as unknown as IntersectionObserver),
    );
  }
  unobserve() {}
  disconnect() {}
}

const DOC = { numPages: 3 } as never; // stable, like the document from usePdfDocument

function Grid({ pages }: { pages: number }) {
  const { thumbs, observe } = usePdfThumbnails(DOC);
  return (
    <ul>
      {Array.from({ length: pages }, (_, i) => i + 1).map((page) => (
        <Item key={page} page={page} observe={observe} ready={thumbs.has(page)} />
      ))}
    </ul>
  );
}

function Item({ page, observe, ready }: { page: number; observe: (el: Element, page: number) => () => void; ready: boolean }) {
  const ref = useCallback((el: HTMLLIElement | null) => (el ? observe(el, page) : undefined), [observe, page]);
  return <li ref={ref}>{ready ? `ready ${page}` : `pending ${page}`}</li>;
}

beforeEach(() => {
  vi.stubGlobal("IntersectionObserver", VisibleObserver);
  URL.revokeObjectURL = vi.fn();
  renderThumbnail.mockClear();
});

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("usePdfThumbnails", () => {
  it("renders visible pages once and revokes every thumbnail URL on unmount", async () => {
    const { unmount } = render(<Grid pages={3} />);
    await waitFor(() => expect(screen.getAllByText(/^ready/)).toHaveLength(3));
    expect(renderThumbnail).toHaveBeenCalledTimes(3);
    expect(URL.revokeObjectURL).not.toHaveBeenCalled();
    unmount();
    expect(vi.mocked(URL.revokeObjectURL).mock.calls.map(([u]) => u).sort()).toEqual([
      "blob:page-1",
      "blob:page-2",
      "blob:page-3",
    ]);
  });
});

describe("usePdfDocument", () => {
  it("reads as loading again right after the file changes", async () => {
    openPdf.mockResolvedValue({ numPages: 4 });
    const a = new Blob(["a"]);
    const b = new Blob(["b"]);
    const { result, rerender } = renderHook(({ file }) => usePdfDocument(file), { initialProps: { file: a } });
    await waitFor(() => expect(result.current.status).toBe("ready"));
    openPdf.mockReturnValue(new Promise(() => undefined));
    rerender({ file: b });
    expect(result.current.status).toBe("loading");
  });
});
