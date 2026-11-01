import Link from "next/link";
import { Bot, Download, Link2, ShieldCheck, SlidersHorizontal, Upload } from "lucide-react";
import { Breadcrumbs } from "@/components/ui/Breadcrumbs";
import { Container } from "@/components/ui/Container";
import { Faq } from "@/components/ui/Faq";
import { JsonLd } from "@/components/ui/JsonLd";
import { StatusBadge } from "@/components/ui/StatusBadge";
import { categoryHref, getCategoryById } from "@/lib/config/categories";
import { getPlan } from "@/lib/config/pricing";
import { retentionSentence } from "@/lib/config/retention";
import { siteConfig } from "@/lib/config/site";
import { acceptLabel, MB } from "@/lib/format";
import { breadcrumbJsonLd, faqJsonLd, toolJsonLd } from "@/lib/seo";
import { getToolsInCategory, hasFileInput, toolHref } from "@/services/catalog";
import type { Tool, Tier } from "@/types/catalog";
import { ToolGrid } from "./ToolGrid";
import { ToolIcon } from "./ToolIcon";
import { ToolWorkspace } from "./ToolWorkspace";

function howItWorks(tool: Tool) {
  const kinds = tool.input_kinds;
  const first = kinds.includes("file")
    ? {
        icon: Upload,
        title: tool.min_inputs > 1 ? "Add your files" : "Add your file",
        text: `Drop or choose ${tool.max_inputs > 1 ? `up to ${tool.max_inputs} files` : "a file"} (${acceptLabel(tool.accepts)}).`,
      }
    : {
        icon: Link2,
        title: tool.min_inputs > 1 ? "Enter the addresses" : "Enter a link",
        text:
          tool.min_inputs > 1
            ? "Paste the addresses of the public web pages you want to use."
            : "Paste the address of a public web page.",
      };
  const requiresAiConsent = (tool as Record<string, unknown>).requires_ai_consent as boolean | undefined;
  return [
    first,
    {
      icon: requiresAiConsent ? Bot : SlidersHorizontal,
      title: requiresAiConsent ? "Choose options and give consent" : "Choose your options",
      text: requiresAiConsent
        ? "Pick your settings, then tick the box to allow this request to be sent to our AI provider."
        : "Adjust the settings if you need to. The defaults work for most documents.",
    },
    {
      icon: Download,
      title: "Download the result",
      text: `Download your result. ${retentionSentence}`,
    },
  ];
}

const FILE_STORAGE_QUESTION = /\bfiles?\b.*\b(stored|kept|keep|store)\b/i;

/**
 * Catalog FAQ, adapted for tools without file input: a "files stored" answer
 * reads wrong for URL/text tools, so it is replaced with one about the input
 * those tools actually take.
 */
export function toolFaq(tool: Tool, fileTool: boolean) {
  const faq = tool.seo.faq ?? [];
  if (fileTool) return faq;
  const kept = faq.filter((item) => !FILE_STORAGE_QUESTION.test(item.question));
  const url = tool.input_kinds.includes("url");
  // Phase 1 only supports file and url input kinds; text input is Phase 2+
  const subject = url ? "the addresses and pages" : "unknown input";
  return [
    ...kept,
    {
      question: `Do you keep ${subject} I submit?`,
      answer: `No. We treat them exactly like files. ${retentionSentence} They are never written to our logs.`,
    },
  ];
}

export function ToolPage({ tool }: { tool: Tool }) {
  const category = getCategoryById(tool.category);
  const path = toolHref(tool);
  const crumbs = [
    { name: "Home", path: "/" },
    { name: "Tools", path: "/tools" },
    ...(category ? [{ name: category.name, path: categoryHref(category) }] : []),
    { name: tool.title, path },
  ];
  const related = getToolsInCategory(tool.category)
    .filter((t) => t.slug !== tool.slug)
    .slice(0, 4);
  const fileTool = hasFileInput(tool);
  const faq = toolFaq(tool, fileTool);
  const tierRequired = ((tool as Record<string, unknown>).tier_required as string | undefined) || "free";
  const plan = getPlan(tierRequired as Tier);
  const jsonLd = [toolJsonLd(tool, path), breadcrumbJsonLd(crumbs), ...(faq.length > 0 ? [faqJsonLd(faq)] : [])];
  const steps = howItWorks(tool);

  return (
    <>
      <JsonLd data={jsonLd} />
      <div className="border-b border-border bg-surface">
        <Container className="py-8 sm:py-12">
          <Breadcrumbs items={crumbs} />
          <div className="flex flex-col gap-4 sm:flex-row sm:items-start">
            <span className="inline-flex size-14 shrink-0 items-center justify-center rounded-2xl bg-accent-soft text-accent-soft-fg">
              <ToolIcon name={tool.icon} className="size-7" />
            </span>
            <div>
              <div className="flex flex-wrap items-center gap-3">
                <h1 className="text-3xl font-bold tracking-tight sm:text-4xl">{tool.title}</h1>
                <StatusBadge status={tool.status} />
              </div>
              <p className="mt-3 max-w-2xl text-lg text-muted">{tool.description}</p>
            </div>
          </div>
          <div className="mt-8 max-w-3xl">
            <ToolWorkspace
              toolSlug={tool.slug}
              title={tool.title}
              status={tool.status}
              inputKinds={tool.input_kinds as ("file" | "url")[]}
              accepts={tool.accepts}
              minInputs={tool.min_inputs}
              maxInputs={Math.min(tool.max_inputs, plan.limits.maxFilesPerJob)}
              maxFileBytes={plan.limits.maxFileMb * MB}
              requiresAiConsent={(tool as Record<string, unknown>).requires_ai_consent as boolean | undefined}
            />
            {fileTool ? (
              <p className="mt-3 text-xs text-muted">
                Limits shown are for the {plan.name} plan.{" "}
                <Link href="/pricing" className="inline-flex min-h-11 items-center underline underline-offset-4 sm:min-h-0">
                  See plan limits
                </Link>
                .
              </p>
            ) : null}
          </div>
        </Container>
      </div>

      <Container className="grid gap-12 py-12 lg:grid-cols-[2fr_1fr]">
        <div className="space-y-12">
          <section aria-labelledby="how-title">
            <h2 id="how-title" className="text-2xl font-bold tracking-tight">
              How it works
            </h2>
            <ol className="mt-5 space-y-4">
              {steps.map((step, index) => (
                <li key={step.title} className="flex gap-4">
                  <span className="inline-flex size-10 shrink-0 items-center justify-center rounded-full bg-accent-soft font-semibold text-accent-soft-fg">
                    {index + 1}
                  </span>
                  <div>
                    <h3 className="flex items-center gap-2 font-semibold">
                      <step.icon aria-hidden="true" className="size-4 text-muted" />
                      {step.title}
                    </h3>
                    <p className="mt-1 text-muted">{step.text}</p>
                  </div>
                </li>
              ))}
            </ol>
          </section>

          {faq.length > 0 ? (
            <section aria-labelledby="faq-title">
              <h2 id="faq-title" className="text-2xl font-bold tracking-tight">
                Questions about {tool.title}
              </h2>
              <div className="mt-5">
                <Faq items={faq} />
              </div>
            </section>
          ) : null}
        </div>

        <aside aria-labelledby="privacy-title" className="h-fit rounded-2xl border border-border bg-surface p-6">
          <h2 id="privacy-title" className="flex items-center gap-2 text-lg font-semibold">
            <ShieldCheck aria-hidden="true" className="size-5 text-success" />
            Privacy note
          </h2>
          <ul className="mt-4 space-y-3 text-sm text-muted">
            <li>{retentionSentence}</li>
            {fileTool ? (
              <li>Your original file names are never stored.</li>
            ) : (
              <li>The addresses and text you submit are never written to our logs.</li>
            )}
            {tool.input_kinds.includes("url") ? (
              <li>We fetch the pages you enter on your behalf, so those websites will see a request from our server, not from you.</li>
            ) : null}
            {((tool as Record<string, unknown>).requires_ai_consent as boolean | undefined) ? (
              <li>
                This is an AI tool. Your content is sent to our AI provider ({siteConfig.aiProviderName}) only after you give
                consent for that request, and the provider&apos;s own retention terms apply.
              </li>
            ) : null}
          </ul>
          <Link href="/security" className="mt-2 inline-flex min-h-11 items-center text-sm font-medium text-accent hover:underline">
            How we protect your files
          </Link>
        </aside>
      </Container>

      {related.length > 0 ? (
        <section aria-labelledby="related-title" className="border-t border-border bg-surface">
          <Container className="py-12">
            <h2 id="related-title" className="mb-6 text-2xl font-bold tracking-tight">
              {category ? `More in ${category.name}` : "Related tools"}
            </h2>
            <ToolGrid tools={related} />
          </Container>
        </section>
      ) : null}
    </>
  );
}
