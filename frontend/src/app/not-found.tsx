import type { Metadata } from "next";
import Link from "next/link";
import { Container } from "@/components/ui/Container";

export const metadata: Metadata = { title: "Page not found" };

export default function NotFound() {
  return (
    <Container className="py-24 text-center">
      <p className="text-sm font-semibold text-accent">404</p>
      <h1 className="mt-2 text-3xl font-bold tracking-tight">Page not found</h1>
      <p className="mt-4 text-muted">The page you are looking for does not exist or has moved.</p>
      <div className="mt-8 flex justify-center gap-4">
        <Link href="/" className="rounded-lg bg-accent px-4 py-2 font-medium text-accent-fg hover:bg-accent-hover">
          Go home
        </Link>
        <Link href="/tools" className="rounded-lg border border-border-strong px-4 py-2 font-medium hover:bg-surface-strong">
          Browse tools
        </Link>
      </div>
    </Container>
  );
}
