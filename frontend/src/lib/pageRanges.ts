/**
 * Page-range parsing and formatting for page-selection UIs.
 *
 * Syntax (1-based): comma-separated page numbers and hyphen ranges, e.g. "1, 5-8".
 * Spaces are ignored around numbers and hyphens, reversed ranges ("8-5") are
 * accepted, and an open end ("5-" or "5-end") runs to the last page. Pages
 * outside 1..total are ignored and reported so the UI can show a hint.
 */

export interface PageRangeParseResult {
  /** Selected pages, 1-based, ascending and unique, all within 1..total. */
  pages: number[];
  /** Parts that are not a page number or range, as typed (trimmed). */
  invalid: string[];
  /** Parts that reference pages outside 1..total, as typed (trimmed). */
  outOfRange: string[];
}

const RANGE = /^(\d+)\s*[-–—]\s*(\d+|end)?$/i;
const SINGLE = /^\d+$/;

/** Parses user input such as "1, 5-8" against a document with `total` pages. */
export function parsePageRanges(input: string, total: number): PageRangeParseResult {
  const selected = new Set<number>();
  const invalid: string[] = [];
  const outOfRange: string[] = [];
  const max = Math.max(0, Math.floor(total));

  for (const raw of input.split(",")) {
    const part = raw.trim();
    if (part === "") continue;

    if (SINGLE.test(part)) {
      const page = Number(part);
      if (page >= 1 && page <= max) selected.add(page);
      else outOfRange.push(part);
      continue;
    }

    const match = RANGE.exec(part);
    if (!match) {
      invalid.push(part);
      continue;
    }
    const a = Number(match[1]);
    const b = match[2] === undefined || match[2].toLowerCase() === "end" ? max : Number(match[2]);
    const lo = Math.min(a, b);
    const hi = Math.max(a, b);
    // Clamp before iterating so "1-999999999" cannot hang the page.
    const from = Math.max(1, lo);
    const to = Math.min(max, hi);
    for (let page = from; page <= to; page += 1) selected.add(page);
    if (lo < 1 || hi > max) outOfRange.push(part);
  }

  return { pages: [...selected].sort((x, y) => x - y), invalid, outOfRange };
}

/**
 * Formats pages as a compact, normalized range string: [1, 5, 6, 7, 8] -> "1, 5-8".
 * Input order and duplicates do not matter; non-positive or non-integer values are dropped.
 */
export function formatPageRanges(pages: Iterable<number>, separator = ", "): string {
  const sorted = [...new Set(pages)].filter((p) => Number.isInteger(p) && p >= 1).sort((x, y) => x - y);
  const parts: string[] = [];
  let i = 0;
  while (i < sorted.length) {
    const start = sorted[i]!;
    let end = start;
    while (i + 1 < sorted.length && sorted[i + 1] === end + 1) {
      i += 1;
      end = sorted[i]!;
    }
    parts.push(start === end ? String(start) : `${start}-${end}`);
    i += 1;
  }
  return parts.join(separator);
}

/**
 * The `pages` option for the backend page tools (backend/app/lib/common.py `parse_pages`):
 * ascending "start-end" ranges and single pages, comma-separated, no spaces.
 */
export function toPagesOption(pages: Iterable<number>): string {
  return formatPageRanges(pages, ",");
}

/** All pages from `from` to `to` inclusive (either order), 1-based. */
export function pageSpan(from: number, to: number): number[] {
  const lo = Math.min(from, to);
  const hi = Math.max(from, to);
  return Array.from({ length: hi - lo + 1 }, (_, k) => lo + k);
}

/**
 * Applies a click on `page` to a selection. A plain click toggles the page; a
 * shift-click with an anchor (the last clicked page) selects every page between
 * the anchor and `page`, inclusive. Returns a new set.
 */
export function applyPageClick(
  selected: ReadonlySet<number>,
  page: number,
  { shift = false, anchor = null }: { shift?: boolean; anchor?: number | null } = {},
): Set<number> {
  const next = new Set(selected);
  if (shift && anchor !== null) {
    for (const p of pageSpan(anchor, page)) next.add(p);
    return next;
  }
  if (next.has(page)) next.delete(page);
  else next.add(page);
  return next;
}
