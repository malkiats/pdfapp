import { describe, expect, it } from "vitest";
import { normalize, searchTools } from "@/lib/search";
import { getToolSummaries } from "@/services/catalog";

const tools = getToolSummaries();

describe("searchTools", () => {
  it("returns nothing for an empty query", () => {
    expect(searchTools(tools, "   ")).toEqual([]);
  });

  it("finds Merge PDF for 'merge' and ranks it first", () => {
    expect(searchTools(tools, "merge")[0]?.slug).toBe("merge-pdf");
  });

  it("matches keywords and multiple terms", () => {
    const slugs = searchTools(tools, "jpg pdf").map((t) => t.slug);
    expect(slugs).toEqual(expect.arrayContaining(["jpg-to-pdf", "pdf-to-jpg"]));
  });

  it("is case and punctuation insensitive", () => {
    expect(searchTools(tools, "PDF-to-WORD")[0]?.slug).toBe("pdf-to-word");
    expect(normalize("Héllo, Wörld!")).toBe("hello world");
  });

  it("requires every term to match", () => {
    expect(searchTools(tools, "merge zzzz")).toEqual([]);
  });

  it("respects the limit", () => {
    expect(searchTools(tools, "pdf", 3)).toHaveLength(3);
  });
});
