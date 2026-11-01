import { Check } from "lucide-react";
import { formatPrice, paidPlansAvailable, plans } from "@/lib/config/pricing";

export function PricingCards({ headingLevel = 3 }: { headingLevel?: 2 | 3 }) {
  const Heading = headingLevel === 2 ? "h2" : "h3";
  return (
    <ul className="grid gap-6 md:grid-cols-3">
      {plans.map((plan) => (
        <li
          key={plan.tier}
          className={`relative flex flex-col rounded-2xl border bg-bg p-6 ${
            plan.highlighted ? "border-accent shadow-md" : "border-border"
          }`}
        >
          {plan.highlighted ? (
            <p className="absolute -top-3 left-6 rounded-full bg-accent px-3 py-0.5 text-xs font-semibold text-accent-fg">
              Most popular
            </p>
          ) : null}
          <Heading className="text-lg font-semibold">{plan.name}</Heading>
          <p className="mt-1 text-sm text-muted">{plan.blurb}</p>
          <p className="mt-5">
            <span className="text-4xl font-bold tracking-tight">{formatPrice(plan.priceUsd)}</span>
            <span className="text-muted"> / month</span>
          </p>
          <dl className="mt-5 grid grid-cols-2 gap-x-4 gap-y-2 rounded-xl bg-surface p-4 text-sm">
            <dt className="text-muted">File size</dt>
            <dd className="text-right font-medium">{plan.limits.maxFileMb} MB</dd>
            <dt className="text-muted">Files per task</dt>
            <dd className="text-right font-medium">{plan.limits.maxFilesPerJob}</dd>
            <dt className="text-muted">Pages per document</dt>
            <dd className="text-right font-medium">{plan.limits.maxPages}</dd>
          </dl>
          <ul className="mt-5 flex-1 space-y-2 text-sm">
            {plan.features.map((feature) => (
              <li key={feature} className="flex gap-2">
                <Check aria-hidden="true" className="mt-0.5 size-4 shrink-0 text-success" />
                <span>{feature}</span>
              </li>
            ))}
          </ul>
          <p className="mt-6 rounded-lg border border-border px-4 py-2.5 text-center text-sm font-medium text-muted">
            {plan.priceUsd === 0 ? "No account needed" : paidPlansAvailable ? "Available now" : "Coming soon"}
          </p>
        </li>
      ))}
    </ul>
  );
}
