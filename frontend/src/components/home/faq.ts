import { formatPrice, getPlan } from "@/lib/config/pricing";
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
    question: "Do I need an account?",
    answer: "No. The free plan works without signing up. Accounts will only be needed for paid plans.",
  },
  {
    question: "Are the AI tools private?",
    answer:
      `AI tools send the content you choose to our AI provider (${siteConfig.aiProviderName}) only after you tick a consent box, every time. The provider's own retention terms apply to what it receives, and our copy is deleted on the same schedule as every other file.`,
  },
  {
    question: "Why are the tools marked as coming soon?",
    answer:
      "We are launching tools in stages, starting with the most common PDF tasks. Each tool page shows how it will work, and uploads open when the tool is ready.",
  },
  {
    question: "How much does it cost?",
    answer: `The free plan costs nothing. ${getPlan("personal").name} (${formatPrice(getPlan("personal").priceUsd)} a month) and ${getPlan("pro").name} (${formatPrice(getPlan("pro").priceUsd)} a month) plans with higher limits will follow once accounts are available.`,
  },
];
