import { describe, expect, it } from "vitest";
import { applyPageClick, formatPageRanges, pageSpan, parsePageRanges, toPagesOption } from "@/lib/pageRanges";

describe("parsePageRanges", () => {
  describe("positive", () => {
    it("parses single pages and ranges into sorted unique pages", () => {
      expect(parsePageRanges("1, 5-8", 10)).toEqual({ pages: [1, 5, 6, 7, 8], invalid: [], outOfRange: [] });
    });

    it("tolerates spaces around numbers, commas and hyphens", () => {
      expect(parsePageRanges("  2 ,4 - 6,  9 ", 10).pages).toEqual([2, 4, 5, 6, 9]);
    });

    it("accepts reversed ranges", () => {
      expect(parsePageRanges("8-5", 10).pages).toEqual([5, 6, 7, 8]);
    });

    it("accepts open-ended ranges and 'end'", () => {
      expect(parsePageRanges("8-", 10).pages).toEqual([8, 9, 10]);
      expect(parsePageRanges("9-END", 10).pages).toEqual([9, 10]);
    });

    it("accepts en dashes and leading zeros", () => {
      expect(parsePageRanges("02–04", 10).pages).toEqual([2, 3, 4]);
    });

    it("merges duplicates and overlaps", () => {
      expect(parsePageRanges("3, 1-4, 3-2, 4", 10).pages).toEqual([1, 2, 3, 4]);
    });
  });

  describe("negative", () => {
    it("reports parts it cannot read and keeps the valid ones", () => {
      const r = parsePageRanges("1, abc, 3-x, 2..4, 5", 10);
      expect(r.pages).toEqual([1, 5]);
      expect(r.invalid).toEqual(["abc", "3-x", "2..4"]);
    });

    it("rejects negative numbers and space-separated lists", () => {
      expect(parsePageRanges("-3", 10).invalid).toEqual(["-3"]);
      expect(parsePageRanges("1 5", 10).invalid).toEqual(["1 5"]);
    });

    it("ignores out-of-range pages with a report", () => {
      const r = parsePageRanges("0, 4, 11", 10);
      expect(r.pages).toEqual([4]);
      expect(r.outOfRange).toEqual(["0", "11"]);
    });

    it("clamps partially out-of-range ranges and reports them", () => {
      const r = parsePageRanges("8-12", 10);
      expect(r.pages).toEqual([8, 9, 10]);
      expect(r.outOfRange).toEqual(["8-12"]);
    });
  });

  describe("edge", () => {
    it("returns nothing for empty input and stray commas", () => {
      expect(parsePageRanges("", 10)).toEqual({ pages: [], invalid: [], outOfRange: [] });
      expect(parsePageRanges(" , ,, ", 10).pages).toEqual([]);
    });

    it("handles a one-page document and a zero-page document", () => {
      expect(parsePageRanges("1", 1).pages).toEqual([1]);
      expect(parsePageRanges("1-", 0)).toEqual({ pages: [], invalid: [], outOfRange: ["1-"] });
    });

    it("does not hang on a huge range", () => {
      const started = Date.now();
      const r = parsePageRanges("1-999999999", 500);
      expect(r.pages).toHaveLength(500);
      expect(Date.now() - started).toBeLessThan(500);
    });

    it("selects every page", () => {
      expect(parsePageRanges("1-3", 3).pages).toEqual([1, 2, 3]);
    });
  });
});

describe("formatPageRanges / toPagesOption", () => {
  it("compacts consecutive pages", () => {
    expect(formatPageRanges([1, 5, 6, 7, 8])).toBe("1, 5-8");
    expect(formatPageRanges(new Set([8, 1, 6, 5, 7, 7]))).toBe("1, 5-8");
    expect(formatPageRanges([2, 3, 10])).toBe("2-3, 10");
  });

  it("handles empty and single input, and drops invalid values", () => {
    expect(formatPageRanges([])).toBe("");
    expect(formatPageRanges([4])).toBe("4");
    expect(formatPageRanges([0, -1, 2.5, 3])).toBe("3");
  });

  it("produces the backend `pages` syntax (no spaces, ascending)", () => {
    expect(toPagesOption([9, 1, 2, 3, 5])).toBe("1-3,5,9");
  });

  it("round-trips with the parser", () => {
    const text = "1, 3-4, 7-10";
    expect(formatPageRanges(parsePageRanges(text, 10).pages)).toBe(text);
  });
});

describe("selection helpers", () => {
  it("pageSpan works in both directions", () => {
    expect(pageSpan(3, 5)).toEqual([3, 4, 5]);
    expect(pageSpan(5, 3)).toEqual([3, 4, 5]);
    expect(pageSpan(2, 2)).toEqual([2]);
  });

  it("a click toggles a page", () => {
    const one = applyPageClick(new Set(), 3);
    expect([...one]).toEqual([3]);
    expect([...applyPageClick(one, 3)]).toEqual([]);
  });

  it("shift+click selects the range from the anchor, in either direction", () => {
    expect([...applyPageClick(new Set([2]), 5, { shift: true, anchor: 2 })].sort()).toEqual([2, 3, 4, 5]);
    expect([...applyPageClick(new Set(), 2, { shift: true, anchor: 6 })].sort()).toEqual([2, 3, 4, 5, 6]);
  });

  it("shift+click without an anchor behaves like a click", () => {
    expect([...applyPageClick(new Set(), 4, { shift: true, anchor: null })]).toEqual([4]);
  });

  it("does not mutate the input set", () => {
    const input = new Set([1]);
    applyPageClick(input, 2);
    expect([...input]).toEqual([1]);
  });
});
