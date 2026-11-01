import Link from "next/link";
import { Container } from "@/components/ui/Container";
import { PageHeader } from "@/components/ui/PageHeader";
import { pageMetadata } from "@/lib/seo";

export const metadata = pageMetadata({
  title: "Subscription",
  description: "Accounts and subscriptions are coming later. You don’t need one to use the free tools.",
  path: "/subscription",
  noIndex: true,
});

export default function SubscriptionPage() {
  return (
    <>
      <PageHeader title="Subscription" description="Accounts and subscriptions are coming later. You don’t need one to use the free tools." />
      <Container className="py-12">
        <Link href="/pricing" className="inline-flex min-h-11 items-center font-medium text-accent underline underline-offset-4">
          See plans and pricing
        </Link>
      </Container>
    </>
  );
}
