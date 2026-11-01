import { expect, test } from "@playwright/test";

test.describe("smoke", () => {
  test("home page loads with hero, landmarks and no console errors", async ({ page }) => {
    const errors: string[] = [];
    page.on("console", (msg) => {
      if (msg.type() === "error") errors.push(msg.text());
    });
    const response = await page.goto("/");
    expect(response?.status()).toBe(200);
    await expect(page.getByRole("heading", { level: 1, name: "Your files. Your privacy. Our tools." })).toBeVisible();
    await expect(page.getByRole("main")).toBeVisible();
    await expect(page.getByRole("contentinfo")).toBeVisible();
    await expect(page.locator('script[type="application/ld+json"]').first()).toBeAttached();
    expect(errors).toEqual([]);
  });

  test("search finds Merge PDF and navigates to its page", async ({ page }) => {
    await page.goto("/");
    await page.getByRole("searchbox", { name: "Search tools" }).fill("merge");
    const result = page.getByRole("list", { name: "Search results" }).getByRole("link").first();
    await expect(result).toContainText("Merge PDF");
    await page.getByRole("searchbox", { name: "Search tools" }).press("Enter");
    await expect(page).toHaveURL(/\/tools\/merge-pdf$/);
  });

  test("tool page renders with a disabled coming-soon upload area", async ({ page }) => {
    const response = await page.goto("/tools/merge-pdf");
    expect(response?.status()).toBe(200);
    await expect(page.getByRole("heading", { level: 1, name: "Merge PDF" })).toBeVisible();
    await expect(page.getByText("Coming soon", { exact: true }).first()).toBeVisible();
    await expect(page.getByRole("button", { name: "Choose files" })).toBeDisabled();
    await expect(page.getByRole("heading", { name: "How it works" })).toBeVisible();
    await expect(page).toHaveTitle(/Merge PDF/);
    const canonical = await page.locator('link[rel="canonical"]').getAttribute("href");
    expect(canonical).toMatch(/\/tools\/merge-pdf$/);
  });

  test("category page and tools index render", async ({ page }) => {
    expect((await page.goto("/tools"))?.status()).toBe(200);
    await expect(page.getByRole("heading", { level: 1, name: "All tools" })).toBeVisible();
    expect((await page.goto("/categories/organize-pdf"))?.status()).toBe(200);
    await expect(page.getByRole("heading", { level: 1, name: "Organize PDF" })).toBeVisible();
  });

  test("unknown tool returns 404", async ({ request }) => {
    expect((await request.get("/tools/does-not-exist")).status()).toBe(404);
    expect((await request.get("/categories/does-not-exist")).status()).toBe(404);
  });

  test("sitemap and robots respond", async ({ request }) => {
    const sitemap = await request.get("/sitemap.xml");
    expect(sitemap.status()).toBe(200);
    expect(await sitemap.text()).toContain("/tools/merge-pdf</loc>");
    const robots = await request.get("/robots.txt");
    expect(robots.status()).toBe(200);
    expect(await robots.text()).toContain("Sitemap:");
  });

  test("security headers are sent", async ({ request }) => {
    const response = await request.get("/");
    const headers = response.headers();
    expect(headers["content-security-policy"]).toContain("frame-ancestors 'none'");
    expect(headers["x-content-type-options"]).toBe("nosniff");
    expect(headers["referrer-policy"]).toBe("strict-origin-when-cross-origin");
    expect(headers["permissions-policy"]).toContain("camera=()");
  });
});
