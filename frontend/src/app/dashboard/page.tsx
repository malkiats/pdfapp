import Link from "next/link";
import { Container } from "@/components/ui/Container";
import { PageHeader } from "@/components/ui/PageHeader";
import { pageMetadata } from "@/lib/seo";

export const metadata = pageMetadata({
  title: "Dashboard",
  description: "Accounts are coming later. You don’t need one to use the free tools.",
  path: "/dashboard",
  noIndex: true,
});

export default function DashboardPage() {
  return (
    <>
      <PageHeader title="Dashboard" description="Accounts are coming later. You don’t need one to use the free tools." />
      <Container className="py-12">
        <Link href="/tools" className="inline-flex min-h-11 items-center font-medium text-accent underline underline-offset-4">
          Browse tools
        </Link>
      </Container>
    </>
  );
}
