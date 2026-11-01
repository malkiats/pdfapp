import Ajv2020 from "ajv/dist/2020";
import addFormats from "ajv-formats";
import { describe, expect, it } from "vitest";
import rawCatalog from "@shared/tool-catalog.json";
import schema from "@shared/tool-catalog.schema.json";
import { catalog, CatalogError, parseCatalog } from "@/lib/catalog";
import { categories, categoryHref } from "@/lib/config/categories";
import { iconMap } from "@/lib/icons";
import { getActiveCategories, getPopularTools, getToolsGroupedByCategory, POPULAR_TOOL_SLUGS } from "@/services/catalog";

describe("shared/tool-catalog.json", () => {
  it("validates against shared/tool-catalog.schema.json (draft 2020-12)", () => {
    const ajv = new Ajv2020({ allErrors: true, strict: false });
    addFormats(ajv);
    const validate = ajv.compile(schema);
    const ok = validate(rawCatalog);
    expect(validate.errors ?? []).toEqual([]);
    expect(ok).toBe(true);
  });

  it("has unique slugs", () => {
    const slugs = catalog.tools.map((t) => t.slug);
    expect(new Set(slugs).size).toBe(slugs.length);
  });

  it("is loaded by the build-time loader without errors", () => {
    expect(catalog.tools.length).toBeGreaterThan(0);
    expect(catalog.schema_version).toBe(1);
  });

  it("only uses icons the frontend can render", () => {
    const missing = catalog.tools.map((t) => t.icon).filter((icon) => !(icon in iconMap));
    expect(missing).toEqual([]);
  });

  it("has a display category for every catalog category", () => {
    const known = new Set(categories.map((c) => c.id));
    const unknown = [...new Set(catalog.tools.map((t) => t.category))].filter((c) => !known.has(c as never));
    expect(unknown).toEqual([]);
  });
});

describe("routing invariants", () => {
  it("keeps category pages and tool pages on separate URL prefixes", () => {
    for (const c of categories) expect(categoryHref(c)).toBe(`/categories/${c.slug}`);
  });

  it("has unique category slugs and icons that render", () => {
    expect(new Set(categories.map((c) => c.slug)).size).toBe(categories.length);
    for (const c of categories) expect(iconMap[c.icon]).toBeDefined();
  });

  it("features only tools that exist", () => {
    expect(getPopularTools().map((t) => t.slug)).toEqual([...POPULAR_TOOL_SLUGS]);
  });

  it("groups every tool exactly once", () => {
    const grouped = getToolsGroupedByCategory().flatMap((g) => g.tools.map((t) => t.slug));
    expect(grouped.sort()).toEqual(catalog.tools.map((t) => t.slug).sort());
    expect(getActiveCategories().length).toBeGreaterThan(0);
  });
});

describe("parseCatalog", () => {
  const valid = structuredClone(rawCatalog) as unknown as { tools: Record<string, unknown>[] };

  it("accepts the real catalog", () => {
    expect(() => parseCatalog(structuredClone(rawCatalog))).not.toThrow();
  });

  it.each([
    ["non-object root", () => null],
    ["wrong schema_version", () => ({ ...valid, schema_version: 2 })],
    ["empty tools", () => ({ ...valid, tools: [] })],
    [
      "duplicate slug",
      () => ({ ...valid, tools: [valid.tools[0], valid.tools[0]] }),
    ],
    ["bad slug", () => ({ ...valid, tools: [{ ...valid.tools[0], slug: "Bad Slug" }] })],
    ["unknown status", () => ({ ...valid, tools: [{ ...valid.tools[0], status: "beta" }] })],
    ["file tool without accepts", () => ({ ...valid, tools: [{ ...valid.tools[0], accepts: [] }] })],
    ["min > max inputs", () => ({ ...valid, tools: [{ ...valid.tools[0], min_inputs: 5, max_inputs: 1 }] })],
    ["missing seo", () => ({ ...valid, tools: [{ ...valid.tools[0], seo: undefined }] })],
  ])("rejects %s", (_name, build) => {
    expect(() => parseCatalog(build())).toThrow(CatalogError);
  });

  it("tolerates an unknown (newer) category", () => {
    const next = { ...valid, tools: [{ ...valid.tools[0], category: "future-category" }] };
    expect(() => parseCatalog(next)).not.toThrow();
  });
});
