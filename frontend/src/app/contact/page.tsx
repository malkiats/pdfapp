import { LifeBuoy, Mail, ShieldAlert, UserCheck } from "lucide-react";
import { Container } from "@/components/ui/Container";
import { PageHeader } from "@/components/ui/PageHeader";
import { PlaceholderTag } from "@/components/ui/PlaceholderTag";
import { siteConfig } from "@/lib/config/site";
import { pageMetadata } from "@/lib/seo";

export const metadata = pageMetadata({
  title: "Contact us",
  description: `Get in touch with the ${siteConfig.name} team about support, privacy questions or security reports.`,
  path: "/contact",
});

const channels = [
  {
    icon: LifeBuoy,
    title: "Support and feedback",
    text: "Problems with a tool, questions about plans, or a feature you would like to see.",
    email: siteConfig.contactEmail,
  },
  {
    icon: UserCheck,
    title: "Privacy questions",
    text: "Questions about how we handle data, or requests about your personal data.",
    email: siteConfig.privacyEmail,
  },
  {
    icon: ShieldAlert,
    title: "Security reports",
    text: "Found a vulnerability? Please report it privately so we can fix it before it is disclosed.",
    email: siteConfig.securityEmail,
  },
] as const;

export default function ContactPage() {
  return (
    <>
      <PageHeader title="Contact us" description="We read every message. Pick the address that fits your question." />
      <Container className="py-12">
        <ul className="grid gap-6 md:grid-cols-3">
          {channels.map((channel) => (
            <li key={channel.title} className="flex flex-col rounded-2xl border border-border p-6">
              <span className="inline-flex size-10 items-center justify-center rounded-lg bg-accent-soft text-accent-soft-fg">
                <channel.icon aria-hidden="true" className="size-5" />
              </span>
              <h2 className="mt-4 text-lg font-semibold">{channel.title}</h2>
              <p className="mt-1 flex-1 text-sm text-muted">{channel.text}</p>
              <p className="mt-4 flex flex-wrap items-center">
                <a
                  href={`mailto:${channel.email}`}
                  className="inline-flex min-h-11 items-center gap-2 break-all text-sm font-medium text-accent hover:underline"
                >
                  <Mail aria-hidden="true" className="size-4 shrink-0" />
                  {channel.email}
                </a>
                <PlaceholderTag />
              </p>
            </li>
          ))}
        </ul>
        <div className="mt-10 max-w-3xl rounded-xl border border-border bg-surface p-5 text-sm text-muted">
          <h2 className="font-semibold text-fg">Please don&apos;t email documents</h2>
          <p className="mt-1">
            To protect your privacy, never attach the files you were working on. Describe the problem instead (tool
            name, file type and approximate size). If a tool showed an error reference, include it; it contains no
            information about your file.
          </p>
        </div>
      </Container>
    </>
  );
}
