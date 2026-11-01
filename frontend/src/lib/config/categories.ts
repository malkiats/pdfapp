/**
 * Presentation data for catalog categories. The category ids come from the
 * contract (ToolCategory enum); `slug` is the SEO-friendly URL segment used at
 * /categories/{slug}. Tools live in their own namespace at /tools/{slug}.
 */
import type { ToolCategory } from "@/types/catalog";

export interface CategoryInfo {
  id: ToolCategory;
  slug: string;
  name: string;
  /** Short label for menus. */
  shortName: string;
  icon: string;
  summary: string;
  intro: string;
  seoTitle: string;
  seoDescription: string;
}

export const categories: readonly CategoryInfo[] = [
  {
    id: "organize" as ToolCategory,
    slug: "organize-pdf",
    name: "Organize PDF",
    shortName: "Organize",
    icon: "layout-grid",
    summary: "Merge, split, reorder and extract pages.",
    intro:
      "Put pages where they belong. Combine several PDFs into one, split a long document, pull out the pages you need or remove the ones you don't.",
    seoTitle: "Organize PDF files online: merge, split, reorder",
    seoDescription:
      "Free online tools to merge, split, reorder, extract and remove PDF pages. Files are deleted automatically after processing.",
  },
  {
    id: "optimize" as ToolCategory,
    slug: "optimize-pdf",
    name: "Optimize PDF",
    shortName: "Optimize",
    icon: "minimize-2",
    summary: "Compress, repair and make PDFs searchable.",
    intro:
      "Make PDFs smaller, fix damaged files and add a searchable text layer to scanned documents.",
    seoTitle: "Optimize PDF online: compress, repair, OCR",
    seoDescription:
      "Compress PDFs, repair damaged files and make scans searchable with OCR. Privacy-first, with automatic file deletion.",
  },
  {
    id: "convert-to-pdf" as ToolCategory,
    slug: "convert-to-pdf",
    name: "Convert to PDF",
    shortName: "To PDF",
    icon: "file-input",
    summary: "Turn images, Office files and web pages into PDF.",
    intro:
      "Convert JPG, PNG, Word, PowerPoint, Excel and HTML files into clean, shareable PDF documents.",
    seoTitle: "Convert files to PDF online: Word, JPG, Excel and more",
    seoDescription:
      "Convert Word, PowerPoint, Excel, JPG, PNG and HTML to PDF. Files are deleted automatically after you download the result.",
  },
  {
    id: "convert-from-pdf" as ToolCategory,
    slug: "convert-from-pdf",
    name: "Convert from PDF",
    shortName: "From PDF",
    icon: "file-output",
    summary: "Turn PDFs into images, Office files or PDF/A.",
    intro:
      "Get your content back out of a PDF as images, editable Office documents or an archival PDF/A file.",
    seoTitle: "Convert PDF online: to Word, JPG, Excel, PowerPoint",
    seoDescription:
      "Convert PDF to Word, Excel, PowerPoint, JPG, PNG or PDF/A. Privacy-first tools with automatic file deletion.",
  },
  {
    id: "edit" as ToolCategory,
    slug: "edit-pdf",
    name: "Edit PDF",
    shortName: "Edit",
    icon: "pencil",
    summary: "Rotate, crop, number, watermark and fill forms.",
    intro:
      "Make changes without installing anything: rotate and crop pages, add page numbers or a watermark, add text and images, and fill in forms.",
    seoTitle: "Edit PDF online: rotate, crop, watermark, page numbers",
    seoDescription:
      "Rotate, crop, watermark, number pages and fill PDF forms online. Files are deleted automatically after processing.",
  },
  {
    id: "security" as ToolCategory,
    slug: "pdf-security",
    name: "PDF Security",
    shortName: "Security",
    icon: "shield-check",
    summary: "Protect, unlock, sign, redact and compare.",
    intro:
      "Add or remove a password, sign documents, permanently redact sensitive content and compare two versions of a PDF.",
    seoTitle: "PDF security tools: protect, unlock, sign, redact",
    seoDescription:
      "Password-protect, unlock, sign, redact and compare PDFs online. Built privacy-first, with automatic file deletion.",
  },
  {
    id: "ocr" as ToolCategory,
    slug: "image-to-text",
    name: "Image to Text (OCR)",
    shortName: "Image to text",
    icon: "scan-text",
    summary: "Extract text from images, scans and screenshots.",
    intro:
      "Pull editable text out of photos, screenshots, receipts, handwriting and scanned documents with optical character recognition.",
    seoTitle: "Image to text online: OCR for photos, scans, receipts",
    seoDescription:
      "Extract text from JPG, PNG, screenshots, receipts and scanned documents with OCR. Files are deleted automatically.",
  },
  {
    id: "ai" as ToolCategory,
    slug: "ai-document-tools",
    name: "AI Document Tools",
    shortName: "AI tools",
    icon: "sparkles",
    summary: "Summarize, translate and ask questions, with consent.",
    intro:
      "Summarize, translate, extract key points or ask questions about a document. AI tools only send content to our AI provider after you agree, every time.",
    seoTitle: "AI document tools: summarize, translate, ask a PDF",
    seoDescription:
      "Summarize PDFs and articles, translate text and ask questions about documents with AI, only with your explicit consent.",
  },
  {
    id: "compare",
    slug: "webpage-comparison",
    name: "Webpage Comparison",
    shortName: "Compare",
    icon: "git-compare-arrows",
    summary: "See what changed between two web pages.",
    intro:
      "Compare the text of two web pages side by side and see exactly what was added, removed or changed.",
    seoTitle: "Compare two webpages online: see what changed",
    seoDescription:
      "Compare the text of two web pages and highlight additions, removals and changes. Privacy-first, no account needed.",
  },
] as const;

for (const [i, c] of categories.entries()) {
  if (categories.findIndex((other) => other.slug === c.slug || other.id === c.id) !== i) {
    throw new Error(`categories.ts: duplicate category slug or id "${c.slug}"`);
  }
}

const byId = new Map<string, CategoryInfo>(categories.map((c) => [c.id, c]));
const bySlug = new Map<string, CategoryInfo>(categories.map((c) => [c.slug, c]));

export function getCategoryById(id: string): CategoryInfo | undefined {
  return byId.get(id);
}

export function getCategoryBySlug(slug: string): CategoryInfo | undefined {
  return bySlug.get(slug);
}

/** Display name for a category id, with a graceful fallback for unknown (newer) categories. */
export function categoryName(id: string): string {
  return byId.get(id)?.name ?? "More tools";
}

export function categoryHref(category: CategoryInfo): string {
  return `/categories/${category.slug}`;
}
