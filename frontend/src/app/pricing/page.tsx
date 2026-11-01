import { PricingCards } from "@/components/pricing/PricingCards";
import { Container } from "@/components/ui/Container";
import { Faq } from "@/components/ui/Faq";
import { JsonLd } from "@/components/ui/JsonLd";
import { PageHeader } from "@/components/ui/PageHeader";
import { formatPrice, getPlan, paidPlansAvailable, plans } from "@/lib/config/pricing";
import { retentionSentence } from "@/lib/config/retention";
import { faqJsonLd, pageMetadata } from "@/lib/seo";
import type { ToolFaqItem } from "@/types/catalog";

export const metadata = pageMetadata({
  title: "Pricing: free, Personal and Pro plans",
  description: `Use the free plan without an account. Personal costs ${formatPrice(getPlan("personal").priceUsd)} and Pro ${formatPrice(getPlan("pro").priceUsd)} a month for bigger files and higher limits.`,
  path: "/pricing",
});

const pricingFaq: ToolFaqItem[] = [
  {
    question: "Is the free plan really free?",
    answer: "Yes. The free plan has no cost and needs no account. It has lower limits on file size, number of files and pages.",
  },
  {
    question: "When can I buy a paid plan?",
    answer:
      "Paid plans arrive together with accounts. Until then every tool is available on the free plan as it launches. Prices shown are in US dollars and may change before launch.",
  },
  {
    question: "Do paid plans keep my files longer?",
    answer: `No. Every plan follows the same deletion schedule. ${retentionSentence}`,
  },
  {
    question: "Who will handle payments?",
    answer:
      "Payments will be handled by a specialised payment provider on its own secure checkout page. We will never see or store your card number.",
  },
];

export default function PricingPage() {
  return (
    <>
      <JsonLd data={faqJsonLd(pricingFaq)} />
      <PageHeader
        title="Simple, fair pricing"
        description="Start free with no account. Upgrade only if you need bigger files or more of them."
      />
      <Container className="py-12">
        {!paidPlansAvailable ? (
          <p className="mb-8 rounded-lg border border-border bg-surface px-4 py-3 text-sm text-muted">
            Paid plans are not on sale yet. They will open together with accounts. Prices are shown in USD per month.
          </p>
        ) : null}
        <PricingCards headingLevel={2} />

        <section aria-labelledby="compare-title" className="mt-16">
          <h2 id="compare-title" className="text-2xl font-bold tracking-tight">
            Compare plan limits
          </h2>
          <p className="mt-2 text-sm text-muted sm:hidden">Scroll sideways to see every plan.</p>
          <div
            role="region"
            aria-label="Plan limits table (scrolls horizontally)"
            tabIndex={0}
            className="mt-3 overflow-x-auto rounded-xl border border-border sm:mt-5"
          >
            <table className="w-full min-w-[32rem] text-left text-sm">
              <caption className="sr-only">Plan limits by tier</caption>
              <thead className="bg-surface">
                <tr>
                  <th scope="col" className="px-4 py-3 font-semibold">
                    Limit
                  </th>
                  {plans.map((plan) => (
                    <th key={plan.tier} scope="col" className="px-4 py-3 font-semibold">
                      {plan.name}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                <tr>
                  <th scope="row" className="px-4 py-3 font-normal text-muted">
                    Price per month
                  </th>
                  {plans.map((plan) => (
                    <td key={plan.tier} className="px-4 py-3">
                      {formatPrice(plan.priceUsd)}
                    </td>
                  ))}
                </tr>
                <tr>
                  <th scope="row" className="px-4 py-3 font-normal text-muted">
                    Maximum file size
                  </th>
                  {plans.map((plan) => (
                    <td key={plan.tier} className="px-4 py-3">
                      {plan.limits.maxFileMb} MB
                    </td>
                  ))}
                </tr>
                <tr>
                  <th scope="row" className="px-4 py-3 font-normal text-muted">
                    Files per task
                  </th>
                  {plans.map((plan) => (
                    <td key={plan.tier} className="px-4 py-3">
                      {plan.limits.maxFilesPerJob}
                    </td>
                  ))}
                </tr>
                <tr>
                  <th scope="row" className="px-4 py-3 font-normal text-muted">
                    Pages per document
                  </th>
                  {plans.map((plan) => (
                    <td key={plan.tier} className="px-4 py-3">
                      {plan.limits.maxPages}
                    </td>
                  ))}
                </tr>
                <tr>
                  <th scope="row" className="px-4 py-3 font-normal text-muted">
                    Maximum processing time
                  </th>
                  {plans.map((plan) => (
                    <td key={plan.tier} className="px-4 py-3">
                      {Math.round(plan.limits.timeoutSeconds / 60)} min
                    </td>
                  ))}
                </tr>
                <tr>
                  <th scope="row" className="px-4 py-3 font-normal text-muted">
                    Automatic file deletion
                  </th>
                  {plans.map((plan) => (
                    <td key={plan.tier} className="px-4 py-3">
                      Yes
                    </td>
                  ))}
                </tr>
              </tbody>
            </table>
          </div>
          <p className="mt-3 text-xs text-muted">
            Limits are enforced by our servers and may be adjusted; the values shown here are for information.
          </p>
        </section>

        <section aria-labelledby="pricing-faq-title" className="mt-16 max-w-3xl">
          <h2 id="pricing-faq-title" className="text-2xl font-bold tracking-tight">
            Pricing questions
          </h2>
          <div className="mt-5">
            <Faq items={pricingFaq} />
          </div>
        </section>
      </Container>
    </>
  );
}
