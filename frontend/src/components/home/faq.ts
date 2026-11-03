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
      "Each task gets a random identifier and a private access token that only your browser holds. Files are processed in isolated workers, and we never store your original file names.",
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
      `AI tools send the content you choose to our AI provider (${siteConfig.aiProviderName}) only after you tick a consent box, every time. The provider's own retention terms apply to what it receives, and our copy is deleted on the same schedule as every other file.`,
  },
  {
    question: "What file size limits are there?",
    answer:
      "No artificial limits. Process files as large as your browser can handle. Processed results are delivered instantly.",
  },
];
