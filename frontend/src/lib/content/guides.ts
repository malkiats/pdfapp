/**
 * How-to guides (/guides). Each one walks through a real tool with the options
 * it actually has; keep them in sync with the tool forms and server limits.
 */

export interface Guide {
  slug: string;
  title: string;
  /** Meta description and card text. */
  description: string;
  /** The tool the guide is about (its page is linked as the call to action). */
  toolSlug: string;
  intro: string;
  steps: { title: string; text: string }[];
  tips: string[];
  faq: { question: string; answer: string }[];
}

export const guides: readonly Guide[] = [
  {
    slug: "reduce-pdf-size-for-email",
    title: "How to reduce a PDF's size for email",
    description:
      "Shrink a large PDF so it fits under email attachment limits, without installing anything. Free, no account.",
    toolSlug: "compress-pdf",
    intro:
      "Many email services reject attachments over about 20–25 MB, and smaller files are faster for everyone. Most of a PDF's size usually comes from images, so compressing those is the quickest win.",
    steps: [
      { title: "Open Compress PDF", text: "Go to the Compress PDF tool. No sign-up is needed." },
      { title: "Add your PDF", text: "Drop the file onto the upload area or choose it from your device." },
      {
        title: "Pick a compression level",
        text: "Medium is a good balance for most documents. Choose High for the smallest file (images get softer), or Low to keep images untouched and only tidy up the file structure.",
      },
      {
        title: "Download and check",
        text: "The page shows how much smaller the file got. Open the result to check that images still look good enough.",
      },
    ],
    tips: [
      "If a PDF is mostly text, it may already be small: compression helps most with scans and photos.",
      "Still too big? Use Split PDF to send it in parts, or Extract pages to send only what is needed.",
      "We never return a file larger than the one you uploaded.",
    ],
    faq: [
      {
        question: "Will compression change my text?",
        answer: "No. Text stays sharp and searchable; only embedded images are recompressed.",
      },
      {
        question: "Is my file kept?",
        answer: "No. Files are deleted automatically, usually within minutes of your download.",
      },
    ],
  },
  {
    slug: "combine-pdf-files",
    title: "How to combine several PDFs into one",
    description: "Merge up to 20 PDF files into a single document in the order you choose. Free and private.",
    toolSlug: "merge-pdf",
    intro:
      "Combining files is handy for sending one tidy document instead of many attachments: a contract and its appendices, scanned receipts, or chapters of a report.",
    steps: [
      { title: "Open Merge PDF", text: "Go to the Merge PDF tool." },
      {
        title: "Add your files",
        text: "Add between 2 and 20 PDFs. They are combined in the order shown in the list, so remove and re-add a file to change its position.",
      },
      {
        title: "Keep bookmarks (optional)",
        text: "Leave “Keep bookmarks” ticked to carry each file's bookmarks into the combined PDF.",
      },
      { title: "Download", text: "Select Merge PDF. The combined file downloads straight away." },
    ],
    tips: [
      "Have photos instead of PDFs? Use JPG to PDF first, then merge.",
      "After merging, Add page numbers gives the combined document consistent numbering.",
      "Password-protected files must be unlocked first (Unlock PDF, with the password).",
    ],
    faq: [
      {
        question: "Is there a limit?",
        answer: "Up to 20 files per merge, within the size limit shown on the tool page.",
      },
      {
        question: "Do I need an account?",
        answer: "No. Every tool works without signing up.",
      },
    ],
  },
  {
    slug: "summarize-a-long-pdf",
    title: "How to summarize a long PDF with AI",
    description:
      "Get a short summary, key points or answers from a long PDF, including scanned documents. Only with your consent.",
    toolSlug: "summarize-pdf",
    intro:
      "Long reports, contracts and papers take time to read. The AI tools give you a quick overview so you know where to focus. They work on scanned PDFs too, by reading the page images.",
    steps: [
      { title: "Open Summarize PDF", text: "Go to the Summarize PDF tool." },
      { title: "Add your PDF", text: "Drop the PDF onto the upload area." },
      { title: "Choose a length", text: "Pick a short, medium or long summary." },
      {
        title: "Give consent and run",
        text: "Tick the box to allow this request to be sent to our AI provider, Groq, then select Summarize PDF. The summary appears on the page, ready to copy.",
      },
    ],
    tips: [
      "Have a specific question? Ask PDF answers it and cites page numbers.",
      "Extract key points lists the main points and any action items or deadlines.",
      "Very long documents are cut to their first part; the result says when that happens.",
      "AI summaries can miss or misread details. Check anything important against the document.",
    ],
    faq: [
      {
        question: "Is my document used to train AI?",
        answer: "We don't use your content for training and don't store prompts or answers. Groq processes it under its own policies, linked in our Privacy Policy.",
      },
      {
        question: "Does it work on scanned PDFs?",
        answer: "Yes. If a PDF has no selectable text, images of its first pages are read by a vision model.",
      },
    ],
  },
  {
    slug: "extract-text-from-image",
    title: "How to copy text from an image or screenshot",
    description:
      "Turn a photo, screenshot or receipt into text you can copy and edit, with AI text recognition. Free, no account.",
    toolSlug: "image-to-text",
    intro:
      "Retyping text from a photo or screenshot is slow and error-prone. Text recognition reads it for you, including tables, receipts and neat handwriting.",
    steps: [
      { title: "Open Image to text", text: "Go to the Image to text tool. It accepts JPG, PNG, WebP and TIFF images." },
      { title: "Add your image", text: "Drop the image onto the upload area. Uncropped, sharp images give the best results." },
      {
        title: "Give consent and run",
        text: "Tick the box to allow the image to be sent to our AI provider, then run the tool.",
      },
      { title: "Copy the text", text: "The text appears on the page. Use Copy, or download it as a text file." },
    ],
    tips: [
      "For receipts and invoices, Receipt to text keeps each item with its amount on one line.",
      "For handwritten notes, Handwriting to text marks words it cannot read as [illegible].",
      "Need the text in another language? Paste it into Translate text.",
    ],
    faq: [
      {
        question: "Which images work best?",
        answer: "Sharp, well-lit images where the text is the right way up. Avoid heavy shadows and very small text.",
      },
      {
        question: "Is my image kept?",
        answer: "No. It is deleted automatically after processing, and we don't store the recognised text.",
      },
    ],
  },
];

export function getGuide(slug: string): Guide | undefined {
  return guides.find((g) => g.slug === slug);
}
