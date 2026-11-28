/**
 * Hand-picked "what next" suggestions and processing tips.
 *
 * These are editorial choices, not usage statistics: the site runs no analytics,
 * so nothing here may be described as "most used" or "trending".
 */

/** Tools that commonly follow a given tool. Unknown or unavailable slugs are skipped. */
export const NEXT_STEPS: Readonly<Record<string, readonly string[]>> = {
  "merge-pdf": ["compress-pdf", "add-page-numbers", "protect-pdf"],
  "split-pdf": ["merge-pdf", "compress-pdf", "pdf-to-jpg"],
  "extract-pages": ["merge-pdf", "compress-pdf"],
  "remove-pages": ["compress-pdf", "add-page-numbers"],
  "organize-pdf": ["add-page-numbers", "compress-pdf"],
  "compress-pdf": ["merge-pdf", "protect-pdf", "pdf-to-word"],
  "repair-pdf": ["compress-pdf", "pdf-to-word"],
  "scan-to-pdf": ["compress-pdf", "summarize-pdf", "merge-pdf"],
  "jpg-to-pdf": ["merge-pdf", "compress-pdf"],
  "png-to-pdf": ["merge-pdf", "compress-pdf"],
  "word-to-pdf": ["compress-pdf", "merge-pdf", "protect-pdf"],
  "powerpoint-to-pdf": ["compress-pdf", "merge-pdf"],
  "excel-to-pdf": ["compress-pdf", "merge-pdf"],
  "html-to-pdf": ["compress-pdf", "merge-pdf"],
  "pdf-to-word": ["summarize-pdf", "translate-pdf", "word-to-pdf"],
  "pdf-to-jpg": ["jpg-to-pdf", "image-to-text"],
  "pdf-to-png": ["png-to-pdf", "image-to-text"],
  "pdf-to-excel": ["excel-to-pdf", "extract-key-points"],
  "pdf-to-powerpoint": ["powerpoint-to-pdf", "summarize-pdf"],
  "rotate-pdf": ["compress-pdf", "merge-pdf"],
  "add-page-numbers": ["compress-pdf", "protect-pdf"],
  "add-watermark": ["protect-pdf", "compress-pdf"],
  "crop-pdf": ["compress-pdf", "merge-pdf"],
  "edit-pdf": ["sign-pdf", "protect-pdf"],
  "sign-pdf": ["protect-pdf", "compress-pdf"],
  "protect-pdf": ["compress-pdf"],
  "unlock-pdf": ["compress-pdf", "pdf-to-word", "merge-pdf"],
  "compare-pdf": ["summarize-pdf", "merge-pdf"],
  "image-to-text": ["translate-text", "extract-key-points"],
  "jpg-to-text": ["translate-text", "extract-key-points"],
  "png-to-text": ["translate-text", "extract-key-points"],
  "screenshot-to-text": ["translate-text", "extract-key-points"],
  "scanned-document-to-text": ["summarize-pdf", "translate-text"],
  "receipt-to-text": ["extract-key-points"],
  "handwriting-to-text": ["translate-text", "extract-key-points"],
  "summarize-pdf": ["ask-pdf", "extract-key-points", "translate-pdf"],
  "summarize-article": ["translate-text", "compare-webpages"],
  "translate-pdf": ["summarize-pdf", "ask-pdf"],
  "translate-text": ["summarize-article"],
  "pdf-to-markdown": ["summarize-pdf", "translate-pdf"],
  "extract-key-points": ["ask-pdf", "summarize-pdf"],
  "ask-pdf": ["summarize-pdf", "extract-key-points"],
  "compare-webpages": ["summarize-article"],
};

/** Short, true facts shown while a request is processing. */
export const PROCESSING_TIPS: readonly string[] = [
  "Merge PDF combines up to 20 files at once, in the order you choose.",
  "Your original file names never leave your browser.",
  "The AI tools can also read scanned PDFs that have no selectable text.",
  "Compare Webpages shows what changed between two versions of a page.",
  "Press / to jump to the tool search on the home page and the tools list.",
  "Ask PDF answers questions about a document and cites the page numbers.",
  "No account is needed for any tool, and nothing is kept after processing.",
  "JPG to PDF turns up to 20 photos into one document.",
];
