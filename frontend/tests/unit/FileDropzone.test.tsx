import { fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { FileDropzone, isAccepted, validateFiles } from "@/components/tools/FileDropzone";

const MB = 1024 * 1024;
const pdf = (name = "a.pdf", size = 1000) => new File([new Uint8Array(size)], name, { type: "application/pdf" });

function setup(props: Partial<Parameters<typeof FileDropzone>[0]> = {}) {
  const onFilesChange = vi.fn();
  render(
    <FileDropzone accept={["application/pdf"]} maxFiles={3} maxFileBytes={MB} onFilesChange={onFilesChange} {...props} />,
  );
  return { onFilesChange, input: screen.getByTestId("file-input") as HTMLInputElement };
}

describe("isAccepted / validateFiles", () => {
  it("matches by MIME type or, when the browser gives none, by extension", () => {
    expect(isAccepted({ name: "x.pdf", type: "application/pdf" }, ["application/pdf"])).toBe(true);
    expect(isAccepted({ name: "x.PDF", type: "" }, ["application/pdf"])).toBe(true);
    expect(isAccepted({ name: "x.png", type: "image/png" }, ["application/pdf"])).toBe(false);
    expect(isAccepted({ name: "anything", type: "" }, [])).toBe(true);
  });

  it("rejects wrong type, oversize, empty and over-count files", () => {
    const big = pdf("big.pdf", MB + 1);
    const empty = pdf("empty.pdf", 0);
    const png = new File(["x"], "img.png", { type: "image/png" });
    const { accepted, rejected } = validateFiles([pdf("1.pdf"), big, empty, png, pdf("2.pdf")], [pdf("0.pdf")], {
      accept: ["application/pdf"],
      maxFiles: 2,
      maxFileBytes: MB,
    });
    expect(accepted.map((f) => f.name)).toEqual(["1.pdf"]);
    expect(rejected.map((r) => r.name)).toEqual(["big.pdf", "empty.pdf", "img.png", "2.pdf"]);
  });
});

describe("FileDropzone", () => {
  it("adds files from the picker, lists them and allows removal", async () => {
    const user = userEvent.setup();
    const { input, onFilesChange } = setup();
    await user.upload(input, [pdf("report.pdf"), pdf("notes.pdf")]);
    const list = screen.getByRole("list", { name: "Selected files" });
    expect(list).toHaveTextContent("report.pdf");
    expect(list).toHaveTextContent("notes.pdf");
    expect(onFilesChange).toHaveBeenLastCalledWith([expect.any(File), expect.any(File)]);
    await user.click(screen.getByRole("button", { name: "Remove report.pdf" }));
    expect(screen.getByRole("list", { name: "Selected files" })).not.toHaveTextContent("report.pdf");
    expect(onFilesChange).toHaveBeenLastCalledWith([expect.objectContaining({ name: "notes.pdf" })]);
  });

  it("accepts dropped files and reports rejected ones accessibly", () => {
    setup();
    const zone = screen.getByTestId("dropzone");
    const files = [pdf("ok.pdf"), new File(["x"], "photo.png", { type: "image/png" })];
    fireEvent.dragOver(zone, { dataTransfer: { files, dropEffect: "none" } });
    expect(zone).toHaveAttribute("data-dragging", "true");
    fireEvent.drop(zone, { dataTransfer: { files } });
    expect(screen.getByRole("list", { name: "Selected files" })).toHaveTextContent("ok.pdf");
    expect(screen.getByRole("alert")).toHaveTextContent("photo.png");
  });

  it("opens the native picker from a keyboard-focusable button", async () => {
    const user = userEvent.setup();
    const { input } = setup();
    const click = vi.spyOn(input, "click");
    const button = screen.getByRole("button", { name: "Choose files" });
    button.focus();
    await user.keyboard("{Enter}");
    expect(click).toHaveBeenCalled();
  });

  it("passes accept and multiple from the catalog to the file input", () => {
    const { input } = setup({ maxFiles: 1 });
    expect(input.accept).toContain("application/pdf");
    expect(input.accept).toContain(".pdf");
    expect(input.multiple).toBe(false);
  });

  it("is fully disabled while the tool is coming soon", () => {
    const { onFilesChange, input } = setup({ disabled: true, disabledReason: "Merge PDF is coming soon." });
    expect(screen.getByRole("button", { name: "Choose files" })).toBeDisabled();
    expect(input).toBeDisabled();
    expect(screen.getByText("Merge PDF is coming soon.")).toBeInTheDocument();
    expect(screen.getByTestId("dropzone")).toHaveAttribute("aria-disabled", "true");
    fireEvent.drop(screen.getByTestId("dropzone"), { dataTransfer: { files: [pdf()] } });
    expect(onFilesChange).not.toHaveBeenCalled();
    expect(screen.queryByRole("list", { name: "Selected files" })).not.toBeInTheDocument();
  });

  it("shows the minimum-files hint until enough files are added", async () => {
    const user = userEvent.setup();
    const { input } = setup({ minFiles: 2 });
    await user.upload(input, [pdf("one.pdf")]);
    expect(screen.getByText(/Add at least 1 more file/)).toBeInTheDocument();
  });
});
