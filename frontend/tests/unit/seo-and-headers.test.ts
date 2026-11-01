import { describe, expect, it } from "vitest";
import sitemap from "@/app/sitemap";
import robots from "@/app/robots";
import { categories, categoryHref } from "@/lib/config/categories";
import { buildCsp, securityHeaders } from "@/lib/security-headers";
import { serializeJsonLd } from "@/lib/seo";
import { getAllTools } from "@/services/catalog";

describe("sitemap and robots", () => {
  it("lists every tool, category and public page, and no private pages", () => {
    const urls = sitemap().map((entry) => new URL(entry.url).pathname);
    for (const tool of getAllTools()) expect(urls).toContain(`/tools/${tool.slug}`);
    for (const category of categories) expect(urls).toContain(categoryHref(category));
    for (const path of ["/", "/tools", "/pricing", "/about", "/contact", "/privacy", "/terms", "/security"]) {
      expect(urls).toContain(path);
    }
    expect(urls).not.toContain("/dashboard");
    expect(new Set(urls).size).toBe(urls.length);
  });

  it("does not disallow private pages, so crawlers can see their noindex tag", () => {
    const rules = robots().rules;
    const list = Array.isArray(rules) ? rules : [rules];
    expect(list[0]?.disallow).toBeUndefined();
  });
});

describe("security headers", () => {
  it("builds a CSP that allows only self and the API origin", () => {
    const csp = buildCsp({ apiBaseUrl: "https://api.example.com/base", isDev: false });
    expect(csp).toContain("connect-src 'self' https://api.example.com");
    expect(csp).toContain("frame-ancestors 'none'");
    expect(csp).toContain("object-src 'none'");
    expect(csp).toContain("upgrade-insecure-requests");
    expect(csp).not.toContain("unsafe-eval");
  });

  it("allows eval and websockets only in development", () => {
    const csp = buildCsp({ apiBaseUrl: "http://localhost:8000", isDev: true });
    expect(csp).toContain("'unsafe-eval'");
    expect(csp).toContain("ws:");
    expect(csp).not.toContain("upgrade-insecure-requests");
  });

  it("sends the baseline hardening headers", () => {
    const keys = securityHeaders({ apiBaseUrl: "https://api.example.com", isDev: false }).map((h) => h.key);
    expect(keys).toEqual(
      expect.arrayContaining([
        "Content-Security-Policy",
        "Referrer-Policy",
        "Permissions-Policy",
        "X-Content-Type-Options",
        "X-Frame-Options",
        "Strict-Transport-Security",
      ]),
    );
  });
});

describe("serializeJsonLd", () => {
  it("cannot break out of the script element", () => {
    const out = serializeJsonLd({ name: "</script><script>alert(1)</script>" });
    expect(out).not.toContain("<");
    expect(JSON.parse(out)).toEqual({ name: "</script><script>alert(1)</script>" });
  });
});
