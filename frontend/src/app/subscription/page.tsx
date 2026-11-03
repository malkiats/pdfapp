import Link from "next/link";
import { Container } from "@/components/ui/Container";
import { PageHeader } from "@/components/ui/PageHeader";
import { pageMetadata } from "@/lib/seo";

export const metadata = pageMetadata({
  title: "Subscription",
  description: "No account needed! All tools are completely free and open source. Start using them now.",
  path: "/subscription",
  noIndex: true,
});

export default function SubscriptionPage() {
  return (
    <>
      <PageHeader
        title="No Account Needed"
        description="All tools are completely free and open source. No account, no limits, no charges ever."
      />
      <Container className="py-12">
        <div className="mb-8 rounded-lg border border-accent bg-accent/5 px-6 py-4">
          <p className="text-lg font-semibold mb-2">Everything is free and always will be 🎉</p>
          <p className="text-muted mb-4">
            Start using any tool immediately without creating an account. All features are included at no cost.
            This is an open-source project created to give everyone access to powerful PDF and document tools.
          </p>
          <div className="flex gap-4 flex-wrap">
            <Link href="/tools" className="inline-flex min-h-11 items-center rounded-lg bg-accent px-6 font-medium text-accent-foreground">
              Use Tools Now
            </Link>
            <Link href="/pricing" className="inline-flex min-h-11 items-center font-medium text-accent underline underline-offset-4">
              Learn More
            </Link>
          </div>
        </div>
      </Container>
    </>
  );
}
