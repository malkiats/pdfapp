/** Serialisable menu data passed from the server header to client menus. */
export interface MenuCategory {
  slug: string;
  name: string;
  summary: string;
  href: string;
  tools: { slug: string; title: string; href: string; comingSoon: boolean }[];
}
