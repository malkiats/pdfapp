/**
 * DISPLAY-ONLY pricing. This file only feeds marketing copy. The server
 * (plans table / settings) is the source of truth for prices and limits, and
 * it enforces them. Never use these values to decide what a user may do.
 */
import type { Tier } from "@/types/catalog";

export interface PlanDisplay {
  tier: Tier;
  name: string;
  /** Monthly price in USD. */
  priceUsd: number;
  blurb: string;
  limits: {
    maxFileMb: number;
    maxFilesPerJob: number;
    maxPages: number;
    timeoutSeconds: number;
  };
  features: string[];
  highlighted?: boolean;
}

export const pricingCurrency = "USD";

/** Paid plans need accounts and payments, which ship in a later phase. */
export const paidPlansAvailable = false;

export const plans: readonly PlanDisplay[] = [
  {
    tier: "free",
    name: "Free",
    priceUsd: 0,
    blurb: "For occasional documents. No account needed.",
    limits: { maxFileMb: 25, maxFilesPerJob: 5, maxPages: 100, timeoutSeconds: 120 },
    features: [
      "All free tools as they launch",
      "Files deleted automatically after processing",
      "No sign-up required",
    ],
  },
  {
    tier: "personal",
    name: "Personal",
    priceUsd: 2.99,
    blurb: "For regular personal use and bigger files.",
    limits: { maxFileMb: 100, maxFilesPerJob: 20, maxPages: 500, timeoutSeconds: 300 },
    features: [
      "Everything in Free",
      "Larger files and more files per task",
      "Longer processing time for big documents",
    ],
    highlighted: true,
  },
  {
    tier: "pro",
    name: "Pro",
    priceUsd: 5.99,
    blurb: "For heavy workloads and the largest files.",
    limits: { maxFileMb: 250, maxFilesPerJob: 20, maxPages: 500, timeoutSeconds: 300 },
    features: [
      "Everything in Personal",
      "The largest file size limit",
      "The highest limits on every tool",
    ],
  },
] as const;

export function formatPrice(priceUsd: number): string {
  if (priceUsd === 0) return "$0";
  return new Intl.NumberFormat("en-US", { style: "currency", currency: pricingCurrency }).format(priceUsd);
}

export function getPlan(tier: Tier): PlanDisplay {
  const plan = plans.find((p) => p.tier === tier);
  if (!plan) throw new Error(`Unknown tier: ${tier}`);
  return plan;
}
