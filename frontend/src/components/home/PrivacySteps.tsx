import { Clock, Cpu, EyeOff, Lock, Trash2, Upload } from "lucide-react";
import { retention, retentionSentence } from "@/lib/config/retention";

/** File lifecycle, kept accurate to docs/privacy.md and docs/architecture.md §1/§4. */
export const privacySteps = [
  {
    icon: Upload,
    title: "Encrypted upload, straight to processing",
    text: "Your browser sends files over HTTPS directly to our processing service. Files never pass through the website host.",
  },
  {
    icon: Cpu,
    title: "Processed in isolation",
    text: "Each task runs in a sandboxed worker with no internet access, separate from every other task.",
  },
  {
    icon: Trash2,
    title: "Inputs deleted when processing ends",
    text: "The files you uploaded are deleted automatically when processing finishes, whether it succeeded or failed.",
  },
  {
    icon: Clock,
    title: "Results deleted automatically",
    text: `Your result is deleted ${retention.afterDownloadMinutes} minutes after your first download, or ${retention.undownloadedMinutes} minutes after it was created if you never download it. You can also delete it yourself at any time.`,
  },
  {
    icon: Lock,
    title: "A safety net for everything else",
    text: `A scheduled cleanup runs every ${retention.sweepEveryMinutes} minutes as a safety net, and a storage expiry rule backs it up. ${retentionSentence}`,
  },
  {
    icon: EyeOff,
    title: "No file names, no content in logs",
    text: "We never store your original file names, and our logs never contain file content, extracted text or the links you compare.",
  },
] as const;

export function PrivacySteps() {
  return (
    <ol className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
      {privacySteps.map((step, index) => (
        <li key={step.title} className="rounded-xl border border-border bg-bg p-5">
          <div className="flex items-center gap-3">
            <span className="inline-flex size-9 items-center justify-center rounded-lg bg-accent-soft text-accent-soft-fg">
              <step.icon aria-hidden="true" className="size-5" />
            </span>
            <span className="text-sm font-medium text-muted">Step {index + 1}</span>
          </div>
          <h3 className="mt-3 font-semibold">{step.title}</h3>
          <p className="mt-1 text-sm text-muted">{step.text}</p>
        </li>
      ))}
    </ol>
  );
}

export function PrivacyLimits() {
  return (
    <div className="rounded-xl border border-border bg-bg p-5 text-sm text-muted">
      <h3 className="font-semibold text-fg">What we don&apos;t claim</h3>
      <p className="mt-2">
        We don&apos;t promise &ldquo;zero retention&rdquo;. Cleanup runs on a schedule, so an outage can delay it. Cloud
        storage providers may keep deleted data in their internal systems for a short time before it is physically
        erased. AI tools send content to our AI provider only after you agree, and that provider&apos;s own retention
        terms apply. Account and billing records, once accounts exist, are kept longer for legal reasons.
      </p>
    </div>
  );
}
