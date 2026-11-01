import Link from "next/link";
import { mainNav } from "@/lib/config/site";
import { categoryHref } from "@/lib/config/categories";
import { getToolsGroupedByCategory, toolHref } from "@/services/catalog";
import { Logo } from "./Logo";
import { MobileNav } from "./MobileNav";
import { ThemeToggle } from "./ThemeToggle";
import { ToolsMenu } from "./ToolsMenu";
import type { MenuCategory } from "./nav-types";

function menuCategories(): MenuCategory[] {
  return getToolsGroupedByCategory().flatMap(({ category, tools }) =>
    category
      ? [
          {
            slug: category.slug,
            name: category.name,
            summary: category.summary,
            href: categoryHref(category),
            tools: tools.map((t) => ({
              slug: t.slug,
              title: t.title,
              href: toolHref(t),
              comingSoon: t.status === "coming_soon",
            })),
          },
        ]
      : [],
  );
}

export function SiteHeader() {
  const categories = menuCategories();
  return (
    <header className="sticky top-0 z-30 border-b border-border bg-bg/95 backdrop-blur supports-[backdrop-filter]:bg-bg/80">
      <div className="mx-auto flex h-16 max-w-6xl items-center justify-between gap-4 px-4 sm:px-6 lg:px-8">
        <Logo />
        <nav aria-label="Main" className="hidden items-center gap-1 lg:flex">
          <ToolsMenu categories={categories} />
          {mainNav.map((item) => (
            <Link
              key={item.href}
              href={item.href}
              className="rounded-lg px-3 py-2 text-sm font-medium text-fg hover:bg-surface-strong"
            >
              {item.label}
            </Link>
          ))}
        </nav>
        <div className="flex items-center gap-1">
          <div className="hidden lg:block">
            <ThemeToggle />
          </div>
          <MobileNav categories={categories} />
        </div>
      </div>
    </header>
  );
}
