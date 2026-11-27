import { LifeBuoy, Mail, ShieldAlert, UserCheck } from "lucide-react";
import { Container } from "@/components/ui/Container";
import { PageHeader } from "@/components/ui/PageHeader";
import { PlaceholderTag } from "@/components/ui/PlaceholderTag";
import { siteConfig } from "@/lib/config/site";
import { pageMetadata } from "@/lib/seo";

export const metadata = pageMetadata({
  title: "Contact us",
  description: `Get in touch with ${siteConfig.name} about support, privacy questions or security reports.`,
  path: "/contact",
});

const topics = [
  {
    icon: LifeBuoy,
    title: "Support and feedback",
    text: "Problems with a tool, feature requests, or general questions. Open source contributions welcome!",
  },
  {
    icon: UserCheck,
    title: "Privacy questions",
    text: "Questions about how we handle data, or requests about your personal data.",
  },
  {
    icon: ShieldAlert,
    title: "Security reports",
    text: "Found a vulnerability? Please report it privately so we can fix it before it is disclosed.",
  },
] as const;

export default function ContactPage() {
  const email = siteConfig.contactEmail;
  return (
    <>
      <PageHeader
        title="Contact us"
        description={`${siteConfig.name} is run by ${siteConfig.ownerName}. We read every message.`}
      />
      <Container className="py-12">
        <div className="max-w-3xl rounded-2xl border border-border p-6">
          <h2 className="text-lg font-semibold">Email us about anything</h2>
          <p className="mt-1 text-sm text-muted">One address for support, privacy and security.</p>
          <p className="mt-4 flex flex-wrap items-center">
            <a
              href={`mailto:${email}`}
              className="inline-flex min-h-11 items-center gap-2 break-all text-base font-medium text-accent hover:underline"
            >
              <Mail aria-hidden="true" className="size-5 shrink-0" />
              {email}
            </a>
            <PlaceholderTag />
          </p>
        </div>
        <ul className="mt-6 grid gap-6 md:grid-cols-3">
          {topics.map((topic) => (
            <li key={topic.title} className="flex flex-col rounded-2xl border border-border p-6">
              <span className="inline-flex size-10 items-center justify-center rounded-lg bg-accent-soft text-accent-soft-fg">
                <topic.icon aria-hidden="true" className="size-5" />
              </span>
              <h2 className="mt-4 text-lg font-semibold">{topic.title}</h2>
              <p className="mt-1 text-sm text-muted">{topic.text}</p>
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
