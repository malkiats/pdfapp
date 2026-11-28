import { retentionSentence } from "@/lib/config/retention";
import { siteConfig } from "@/lib/config/site";
import type { ToolFaqItem } from "@/types/catalog";

export const homeFaq: ToolFaqItem[] = [
  {
    question: `Does ${siteConfig.name} keep my files?`,
    answer: `Only for as long as processing and your download need them. ${retentionSentence}`,
  },
  {
    question: "Can anyone else see my documents?",
    answer:
      "No. Your files travel over HTTPS to our processing service, are used only for your request, and are then deleted automatically. Large-file downloads use short-lived private links that only your browser receives. We never store your original file names, and our logs never contain file contents.",
  },
  {
    question: "Do I need an account or pay anything?",
    answer: "No. Everything is completely free with no account required. No ads, no hidden charges, no subscriptions. Ever.",
  },
  {
    question: "Is this really open source?",
    answer:
      "Yes! The full source code is available on GitHub. You can self-host it, review the code for security, or contribute improvements.",
  },
  {
    question: "Are the AI tools private?",
    answer:
      `AI tools and image to text tools send the content you choose to our AI provider (${siteConfig.aiProviderName}) only after you tick a consent box, every time. The provider's own retention terms apply to what it receives, and our copy is deleted on the same schedule as every other file.`,
  },
  {
    question: "What file size limits are there?",
    answer:
      "Files up to about 4 MB are processed straight away. Larger files, up to 100 MB each, are uploaded to temporary storage first and deleted after processing. PDFs can have up to 100 pages (2,000 for large uploads), and AI tools read the first part of very long documents.",
  },
];
